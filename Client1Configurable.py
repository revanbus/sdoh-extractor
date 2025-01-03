import sys
# sys.path.insert(1, './MyUtils/V3_2')
# from myUtils import MyDB
import os
import sys
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
from BaseExtractor import SDOHBaseExtractor
from loguru import logger
import argparse


class Client1DataProcessor(SDOHBaseExtractor):
    def __init__(self, start_num=0, end_num=None, src_table=None, src_col=None, tgt_table=None, tgt_col=None):
        SDOHBaseExtractor.__init__(self)
        self.src_table    = src_table
        self.src_col      = src_col
        self.tgt_col      = tgt_col
        self.tgt_table    = tgt_table
        self.target_table = tgt_table  # does this need to move to the child class?
        self.src_db       = MyDB('staging_client1', 'dev99')
        self.modelID      = "anthropic.claude-3-haiku-20240307-v1:0"
        self.llm          = ChatBedrock(
            model_id=self.modelID,
            client=self.bedrock_client,
            model_kwargs={"temperature": 0.1}  # using a low temperature because don't need creative responses
        )
        self.prompt_template_file = 'prompt_cc_code.txt'
        self.prompt               = SDOHBaseExtractor.load_prompt(self.prompt_template_file)
        self.bedrock_chain        = self.prompt | self.llm
        self.start_num            = start_num
        if end_num is None:
            self.end_where_clause     = ''
        else:
            self.end_where_clause     = f'AND t1.row_seq_no <= {end_num} '

    def extract_data(self):
        """SELECT the data for the prompts from RDS"""

        # SELECT the rows from the source that aren't already in the target DB,
        # constrained by the WHERE clause
        sql = f"""SELECT t1.{self.src_col}, t1.row_seq_no
                    FROM {self.src_table} t1
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM {self.tgt_table} t2
                        WHERE t2.row_seq_no = t1.row_seq_no
                    ) AND t1.{self.src_col} <> ''
                    AND t1.{self.src_col} ~ '[a-zA-Z]'
                    AND t1.{self.src_col} IS NOT NULL
                    AND t1.row_seq_no >{self.start_num}
                    {self.end_where_clause}
                    LIMIT 10;"""
        logger.info("SQL for record selection set")
        logger.info(sql)
        data = self.src_db.runTheQuery(sql, returnSomething=True)
        return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='llmExtractor')
    parser.add_argument('-sn', '--start_num', help='Int index to start parsing at', default=0)
    parser.add_argument('-en', '--end_num', help='Int index to end parsing at', default=None)
    parser.add_argument('-st', '--src_table', help='Source table')
    parser.add_argument('-sc', '--src_col', help='Source column')
    parser.add_argument('-tt', '--tgt_table', help='Target table')
    parser.add_argument('-tc', '--tgt_col', help='Target column')
    args   = parser.parse_args()

    client_a_extractor = Client1DataProcessor(start_num=args.start_num, end_num=args.end_num, src_table=args.src_table,
                                              src_col=args.src_col, tgt_table=args.tgt_table, tgt_col=args.tgt_col)
    client_a_extractor.run()
