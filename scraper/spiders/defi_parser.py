import scrapy
from scrapy.selector import Selector
import os
import pandas as pd
import json
from config import MAX_TRANSACTIONS

class DefiParserSpider(scrapy.Spider):
    name = "defi_parser"

    headers = {
        "Host": "api-v2.solscan.io",
        "User-Agent": "Mozilla/5.0 (Linux; x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Origin": "https://solscan.io",
        "Alt-Used": "api-v2.solscan.io",
        "Connection": "keep-alive",
        "Referer": "https://solscan.io/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
        "TE": "trailers"
    }
    
    def __init__(self, address='', output_dir='', filename='output.csv', custom_url='', *args, **kwargs):
        super(DefiParserSpider, self).__init__(*args, **kwargs)
        self.address = address
        self.base_url = custom_url
        self.path = os.path.join(output_dir, filename)
        self.page = 1
        self.total_transactions = 0
        self.max_transactions = MAX_TRANSACTIONS  # Maximum de transactions à récupérer

    def start_requests(self):
        yield scrapy.Request(url=self.base_url.format(page=self.page), callback=self.parse, headers=self.headers)

    def parse(self, response):
        raw_data = response.body
        data = json.loads(raw_data)
        transactions = data.get('data', [])

        # Create a DataFrame from the transactions
        df = pd.DataFrame([{
            "block_id": tx["block_id"],
            "trans_id": tx["trans_id"],
            "block_time": tx["block_time"],
            "token1": tx["amount_info"]["token1"],
            "token2": tx["amount_info"]["token2"],
            "decimal1": tx["amount_info"]["token1_decimals"],
            "decimal2": tx["amount_info"]["token2_decimals"],
            "amount1": tx["amount_info"]["amount1"],
            "amount2": tx["amount_info"]["amount2"],
            "activity_type": tx["activity_type"]
        } for tx in transactions])

        # Append to the CSV file
        if not os.path.isfile(self.path):
            df.to_csv(self.path, index=False)
        else:
            df.to_csv(self.path, mode='a', header=False, index=False)

        self.total_transactions += len(transactions)

        # Check if the number of transactions exceeds the maximum allowed
        if self.total_transactions >= self.max_transactions:
            self.logger.warn(f"Reached the maximum limit of {self.max_transactions} transactions for {self.address}. Skipped")
            return

        # Check if there are more transactions to fetch
        if len(transactions) == 100:
            self.page += 1
            next_url = self.base_url.format(page=self.page)
            yield scrapy.Request(url=next_url, callback=self.parse, headers=self.headers)
        else:
            self.logger.info(f"Total transactions for {self.address}: {self.total_transactions}")