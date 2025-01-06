# SDOH Extractor

The SDOH extractor code is a portfolio example of proof-of-concept code I wrote. It is a utility designed to extract unstructured case notes and search for social determinants of health (SDOH) along with chronic conditions using a Large Language Model (LLM). The extracted output is stored in an RDS PostGRES table. If a failure occurs, the process can be restarted, and it will automatically identify any inferences that haven't been processed and run them. It is provided as an example of coding style.

## Prerequisites

Before you begin, ensure you have the following:

1. **AWS Profile Configuration**
   - Create an AWS CLI profile named `my_aws_profile`.
   - The profile must have permissions to perform AWS Bedrock inferences.
     - Refer to the [AWS Bedrock Documentation](https://docs.aws.amazon.com/) for details on required permissions and policy setup.
   - To configure the profile:
     ```bash
     aws configure --profile my_aws_profile
     ```

2. **Python 3.10 Installed**
   - This project requires Python version 3.10. You can check your Python version using:
     ```bash
     python --version
     ```

## Setting Up the Environment

1. **Clone the Repository**
   - Clone this repository to your local machine:
     ```bash
     git clone https://github.com/revanbus/sdoh-extractor.git
     cd sdoh-extractor
     ```

2. **Create a Virtual Environment**
   - Create a virtual environment using Python 3.10:
     ```bash
     python3.10 -m venv venv
     ```
   - Activate the virtual environment:
     - On Linux/macOS:
       ```bash
       source venv/bin/activate
       ```
     - On Windows:
       ```bash
       .\venv\Scripts\activate
       ```

3. **Install Dependencies**
   - Install the required dependencies from `requirements.txt`:
     ```bash
     pip install -r requirements.txt
     ```

## Usage

1. **Ensure AWS Credentials Are Active**
   - Make sure your AWS profile `my_aws_profile` is correctly set up and contains valid credentials.
   - You can check the profile using:
     ```bash
     aws sts get-caller-identity --profile my_aws_profile
     ```

2. **Create the Output Table**
   - Before running the application, ensure the output table is created in your database. Use the following DDL script to create the table:
     ```sql
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
     ```

3. **Run the Application**
   - The main entry point for the application is through client-specific scripts that inherit functionality from the base class `BaseExtractor.py`. For example, to run the client-specific script `Client1Configurable.py`, use the following command:
     ```bash
     python Client1Configurable.py -sn <start_num> -en <end_num> -st <src_table> -sc <src_col> -tt <tgt_table> -tc <tgt_col>
     ```
   - The script requires the following command-line arguments:
     - `-sn`, `--start_num`: Integer index to start parsing at (default: `0`).
     - `-en`, `--end_num`: Integer index to end parsing at (default: `None`).
     - `-st`, `--src_table`: Name of the source table.
     - `-sc`, `--src_col`: Name of the source column.
     - `-tt`, `--tgt_table`: Name of the target table.
     - `-tc`, `--tgt_col`: Name of the target column.

   - **Client-Specific Implementation**
     - Each client will require their own version of the configurable file (e.g., `Client1Configurable.py`), tailored to their specific requirements.
     - The configurable file should inherit and extend the functionality of the base class `BaseExtractor.py`.

## License

This project is licensed under the MIT License. See the LICENSE file for details.
