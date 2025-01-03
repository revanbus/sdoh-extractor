import sys
# sys.path.insert(1, './MyUtils/V3_2')
# from myUtils import MyDB
import os
import boto3
import json
import pprint
from tabulate import tabulate
from langchain.chains import LLMChain
# from langchain.llms.bedrock import Bedrock
from langchain_aws import BedrockLLM
from langchain_aws import ChatBedrock
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from typing import Union, List
import re
import hashlib
from loguru import logger


class SDOHBaseExtractor:
    def __init__(self):
        self.empty_response = {
            "error": "Please check"
        }
        os.environ["AWS_PROFILE"] = "my_aws_profile"
        self.bedrock_client       = boto3.client(
            service_name="bedrock-runtime",
            region_name="us-east-1"
        )

        self.last_encrypted_id = ''  # used for skipping processing duplicate rows

    @staticmethod
    def load_prompt(prompt_template_file):
        # get prompt template from file
        with open(prompt_template_file, 'r') as file:
            template_txt = file.read()

        prompt = PromptTemplate(
            input_variables=["note"],
            template=template_txt
        )

        return prompt

    def extract_data(self):
        """This is for extracting the prompt data from the source and has to be implemented in child class"""
        raise NotImplementedError

    def process_llm_response(self, response):
        # Restrictive regex to capture JSON with "detected_diseases" field
        response   = str(response)  # ensure we are sending a string
        json_match = re.search(r'{.*}', response, re.DOTALL)

        if json_match:
            json_str = json_match.group(0)
            try:
                # Convert the string to a JSON object
                json_str = json_str.replace('False', 'false')
                json_str = json_str.replace('True', 'true')
                json_str = str(json_str).replace(r"\_", "_")
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding JSON: {e}")
                logger.error(json_str)
                return self.empty_response
        else:
            logger.error("No valid JSON found.")
            return self.empty_response

    def store_data(self, metadata):
        """Store the results in PostGRES or wherever"""
        """ INSERT INTO llm.tgt_clientmedical
                        (row_seq_no, medical_cmts, llm_full_response, food, housing, transportation, care_management, 
                         chronic_conditions)
                        VALUES(0, '', '', '', '', '', '', ?);"""
        """metadata = {"row_seq_no": row_seq_id, "medical_cmts": the_prompt, "llm_full_response": response,
                    "json_response": json_response,
                    "food": food_need, "housing": housing_need, "transportation": transportation_need,
                    "care_management": care_management_need,
                    "chronic_conditions": json_response['chronic_conditions'], "error_msg": "not implemented"}"""
        # row variables
        row_seq_no    = metadata['row_seq_no']
        src_txt       = metadata['medical_cmts']
        src_txt       = src_txt.replace("'", '"')
        full_response = metadata['llm_full_response']
        full_response = full_response.replace("'", '"')

        food            = metadata['food']
        housing         = metadata['housing']
        transportation  = metadata['transportation']
        care_management = metadata['care_management']
        chronic_conditions = str(metadata['chronic_conditions'])
        chronic_conditions = chronic_conditions.replace('"', "'")  # ARRAY format must have single quotes
        error_msg       = metadata['error_msg']  # TODO

        # UPSERT query
        upsert_query = f"""
            INSERT INTO {self.target_table}
                        (row_seq_no, {self.tgt_col}, llm_full_response, food, housing, transportation, care_management, 
                         chronic_conditions, error_message)
                        VALUES('{row_seq_no}', '{src_txt}', '{full_response}', '{food}', '{housing}', 
                        '{transportation}', '{care_management}', ARRAY {chronic_conditions}::VARCHAR[], '{error_msg}')
            ON CONFLICT (row_seq_no)
            DO UPDATE SET
                {self.tgt_col}     = EXCLUDED.{self.tgt_col},
                llm_full_response  = EXCLUDED.llm_full_response,
                food               = EXCLUDED.food,
                housing            = EXCLUDED.housing,
                transportation     = EXCLUDED.transportation,
                care_management    = EXCLUDED.care_management,
                chronic_conditions = EXCLUDED.chronic_conditions,
                error_message      = EXCLUDED.error_message
            RETURNING *;
        """
        # logger.info(upsert_query)
        try:
            self.src_db.runTheQuery(upsert_query, returnSomething=False)
        except Exception as e:
            logger.error(f"An error occurred {e}")

    @staticmethod
    def md5_str(string_to_hash):

        # Create an MD5 hash object
        md5_hash = hashlib.md5()

        # Update the hash object with the string, encoded to bytes
        md5_hash.update(string_to_hash.encode('utf-8'))

        # Get the hexadecimal representation of the hash
        hash_result = md5_hash.hexdigest()

        logger.debug(f"The MD5 hash is: {hash_result}")
        return hash_result

    def run(self):
        """Main method that orchestrates the class functions"""
        data           = self.extract_data()
        i = 0
        for the_row in data:
            the_prompt     = the_row[0]  # first column is always the text for the prompt
            row_seq_id   = str(the_row[1])
            logger.info(f'Running row {i} row_seq({row_seq_id})')
            i = i + 1
            response      = self.send_to_llm(the_prompt)
            json_response = self.process_llm_response(response)
            json_response = json.dumps(json_response)
            json_response = str(json_response).replace("'", "''")
            json_response = json.loads(json_response)
            logger.debug(json_response)

            if 'error' in json_response:
                chronic_conditions = []
            else:
                chronic_conditions = json_response['chronic_conditions']

            """ INSERT INTO llm.tgt_clientmedical
                (row_seq_no, medical_cmts, llm_full_response, food, housing, transportation, care_management, 
                chronic_conditions)
                VALUES(0, '', '', '', '', '', '', ?);"""

            care_management_need, food_need, housing_need, transportation_need, err_msg = \
                self.parse_json_response(json_response)

            metadata = {"row_seq_no": row_seq_id, "medical_cmts": the_prompt, "llm_full_response": response,
                        "json_response": json_response, "food": food_need, "housing": housing_need,
                        "transportation": transportation_need, "care_management": care_management_need,
                        "chronic_conditions": chronic_conditions, "error_msg": err_msg}
            self.store_data(metadata)

    def parse_json_response(self, json_response):

        if 'error' in json_response:
            food_need            = 'N'
            housing_need         = 'N'
            transportation_need  = 'N'
            care_management_need = 'N'
            err_msg              = 'Error: check full response'

            return care_management_need, food_need, housing_need, transportation_need, err_msg

        err_msg = ''
        if json_response['food']:
            food_need = 'Y'
        else:
            food_need = 'N'

        if json_response['housing']:
            housing_need = 'Y'
        else:
            housing_need = 'N'

        if json_response['transportation']:
            transportation_need = 'Y'
        else:
            transportation_need = 'N'

        if json_response['care_management']:
            care_management_need = 'Y'
        else:
            care_management_need = 'N'

        return care_management_need, food_need, housing_need, transportation_need, err_msg

    def send_to_llm(self, the_note):
        """Call the LLM API"""
        try:
            # Execute LangChain
            response     = self.bedrock_chain.invoke({'note': the_note})
            response_txt = response.content

        except ValueError as e:
            # Capture any errors
            logger.error("Error: The LLM response was not in the expected JSON format.")
            error_msg = str(e)
            logger.error(f"Details: {error_msg}")

            # Return error JSON
            response_txt = {"error": "Invalid JSON", "raw_response": "TBD"}  # TODO How to respond to errors?

        return response_txt


"""
-- Output table DDL
-- llm.tgt_clientmedical definition

-- Drop table

-- DROP TABLE llm.tgt_clientmedical;

CREATE TABLE llm.tgt_clientmedical (
	row_seq_no int4 NULL,
	medical_cmts varchar NULL,
	llm_full_response varchar NULL,
	food bpchar(1) NULL,
	housing bpchar(1) NULL,
	transportation bpchar(1) NULL,
	care_management bpchar(1) NULL,
	chronic_conditions _varchar NULL,
	CONSTRAINT tgt_clientmedical_pk PRIMARY KEY (row_seq_no)
);
"""
