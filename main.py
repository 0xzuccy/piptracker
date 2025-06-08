import os
from dotenv import load_dotenv
import asyncio
import json
from web3 import Web3
from telegram import Bot
import requests
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

# HyperEVM Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
HYPEREVM_RPC = 'https://rpc.hyperliquid.xyz/evm'
CONTRACT_ADDRESS = '0xb6c73F6c09f850651DCb6D62a4D3A7F25e0016C4'
CHAIN_ID = 999

# Initialize Web3 for HyperEVM
web3 = Web3(Web3.HTTPProvider(HYPEREVM_RPC))
bot = Bot(token=BOT_TOKEN)


class HyperEVMNFTTracker:
    def __init__(self):
        self.contract_address = CONTRACT_ADDRESS.lower()
        self.last_processed_block = web3.eth.block_number
        self.function_signatures = {
            'buyItems': None,
            'acceptBids': None
        }

    async def track_transactions(self):
        """Main tracking loop for HyperEVM"""
        print(f"🚀 Starting HyperEVM NFT Tracker...")
        print(f"📊 Connected to HyperEVM (Chain ID: {CHAIN_ID})")
        print(f"🔍 Tracking contract: {CONTRACT_ADDRESS}")
        print(f"📈 Current block: {self.last_processed_block}")

        while True:
            try:
                current_block = web3.eth.block_number

                # Process new blocks
                for block_num in range(self.last_processed_block + 1, current_block + 1):
                    await self.process_block(block_num)

                self.last_processed_block = current_block
                await asyncio.sleep(5)

            except Exception as e:
                print(f"❌ Error in tracking: {e}")
                await asyncio.sleep(15)

    async def process_block(self, block_number):
        """Process a single HyperEVM block"""
        try:
            block = web3.eth.get_block(block_number, full_transactions=True)

            for tx in block.transactions:
                if tx.to and tx.to.lower() == self.contract_address:
                    await self.analyze_transaction(tx, block_number)

        except Exception as e:
            print(f"❌ Error processing block {block_number}: {e}")

    async def analyze_transaction(self, tx, block_number):
        """Analyze HyperEVM transaction for NFT purchases"""
        try:
            receipt = web3.eth.get_transaction_receipt(tx.hash)

            if receipt.status != 1:
                return

            if tx.input and len(tx.input) >= 10:
                await self.handle_nft_transaction(tx, receipt, block_number)

        except Exception as e:
            print(f"❌ Error analyzing transaction {tx.hash.hex()}: {e}")

    async def extract_token_ids_from_logs(self, logs):
        """Extract token IDs from Transfer events, BidAccepted events, and ItemSold events"""
        token_ids = []
        event_details = []

        try:
            # Event signatures
            transfer_topic = web3.keccak(text="Transfer(address,address,uint256)").hex()
            bid_accepted_topic = "0xf6b2b7813b1815a0e2e32964b4f22ec24862322d9c9c0e0eefac425dfc455ab1"
            item_sold_topic = "0x72d3f914473a393354e6fcd9c3cb7d2eee53924b9b856f9da274e024566292a5"

            for log in logs:
                # Handle Transfer events (for general NFT transfers)
                if (len(log.topics) >= 4 and
                        log.topics[0].hex() == transfer_topic and
                        log.address.lower() == self.contract_address):
                    token_id = int(log.topics[3].hex(), 16)
                    token_ids.append(token_id)

                # Handle BidAccepted events
                elif log.topics[0].hex() == bid_accepted_topic:
                    bid_data = await self.decode_bid_accepted_event(log)
                    if bid_data and 'tokenId' in bid_data:
                        token_ids.append(bid_data['tokenId'])
                        event_details.append(('BidAccepted', bid_data))

                # Handle ItemSold events
                elif log.topics[0].hex() == item_sold_topic:
                    item_sold_data = await self.decode_item_sold_event(log)
                    if item_sold_data and 'tokenId' in item_sold_data:
                        token_ids.append(item_sold_data['tokenId'])
                        event_details.append(('ItemSold', item_sold_data))

        except Exception as e:
            print(f"❌ Error extracting token IDs: {e}")

        return token_ids, event_details

    async def decode_bid_accepted_event(self, log):
        """Decode BidAccepted event to extract detailed information"""
        try:
            # The BidAccepted event structure based on your data:
            # bidType, bidder, nftAddress, paymentToken, pricePerItem, quantity, seller, tokenId

            # Decode the data field (contains non-indexed parameters)
            data = log.data[2:]  # Remove '0x' prefix

            # Split data into 32-byte chunks
            chunks = [data[i:i + 64] for i in range(0, len(data), 64)]

            if len(chunks) >= 8:  # Ensure we have enough data
                bid_type = int(chunks[0], 16)
                price_per_item = int(chunks[2], 16)
                quantity = int(chunks[3], 16)
                token_id = int(chunks[7], 16)  # tokenId is typically the last parameter

                # Extract indexed parameters from topics
                bidder = "0x" + log.topics[1].hex()[26:]  # Remove padding
                nft_address = "0x" + log.topics[2].hex()[26:]  # Remove padding
                seller = "0x" + log.topics[3].hex()[26:] if len(log.topics) > 3 else "Unknown"

                return {
                    'tokenId': token_id,
                    'bidType': bid_type,
                    'bidder': bidder,
                    'nftAddress': nft_address,
                    'pricePerItem': price_per_item,
                    'quantity': quantity,
                    'seller': seller,
                    'paymentToken': 'WHYPE'  # Based on your data
                }

        except Exception as e:
            print(f"❌ Error decoding BidAccepted event: {e}")

        return None

    async def decode_item_sold_event(self, log):
        """Decode ItemSold event to extract detailed information"""
        try:
            # ItemSold event structure based on your data:
            # buyer, nftAddress, paymentToken, pricePerItem, quantity, seller, tokenId

            data = log.data[2:]  # Remove '0x' prefix
            chunks = [data[i:i + 64] for i in range(0, len(data), 64)]

            if len(chunks) >= 6:  # Ensure we have enough data
                # Extract indexed parameters from topics
                buyer = "0x" + log.topics[1].hex()[26:] if len(log.topics) > 1 else "Unknown"
                nft_address = "0x" + log.topics[2].hex()[26:] if len(log.topics) > 2 else "Unknown"
                seller = "0x" + log.topics[3].hex()[26:] if len(log.topics) > 3 else "Unknown"

                # Extract non-indexed parameters from data
                price_per_item = int(chunks[0], 16)  # pricePerItem
                quantity = int(chunks[1], 16)  # quantity
                token_id = int(chunks[2], 16)  # tokenId

                return {
                    'tokenId': token_id,
                    'buyer': buyer,
                    'seller': seller,
                    'nftAddress': nft_address,
                    'pricePerItem': price_per_item,
                    'quantity': quantity,
                    'paymentToken': 'WHYPE'  # Based on your data
                }

        except Exception as e:
            print(f"❌ Error decoding ItemSold event: {e}")

        return None

    async def handle_nft_transaction(self, tx, receipt, block_number):
        """Enhanced handler for NFT transactions with both ItemSold and BidAccepted events"""
        try:
            tx_hash = tx.hash.hex()
            buyer = tx['to']
            seller = tx['from']
            gas_used = receipt.gasUsed
            gas_price = tx.gasPrice

            gas_cost_wei = gas_used * gas_price
            gas_cost_hype = web3.from_wei(gas_cost_wei, 'ether')

            # Extract token IDs and event details
            token_ids, event_details = await self.extract_token_ids_from_logs(receipt.logs)

            tx_value_hype = web3.from_wei(tx.value, 'ether') if tx.value > 0 else 0

            # Process each event type
            for event_type, event_data in event_details:
                if event_type == "ItemSold":
                    await self.send_item_sold_notification(event_data, tx_hash, gas_used, gas_cost_hype, block_number)
                elif event_type == "BidAccepted":
                    await self.send_bid_accepted_notification(event_data, tx_hash, gas_used, gas_cost_hype,
                                                              block_number)

            # If no specific events found, send generic notification
            if not event_details and token_ids:
                await self.send_generic_notification(token_ids, buyer, seller, tx_value_hype, tx_hash, gas_used, gas_cost_hype,
                                                     block_number)

        except Exception as e:
            print(f"❌ Error handling NFT transaction: {e}")

    async def send_item_sold_notification(self, item_data, tx_hash, gas_used, gas_cost_hype, block_number):
        """Send notification for ItemSold events"""
        try:
            price_hype = web3.from_wei(item_data['pricePerItem'], 'ether')

            message = f"""
PiP & Friends {', '.join(map(str, item_data['tokenId'])) if item_data['tokenId'] else 'Unknown'} was bought for {price_hype:.6f} HYPE

from: '{item_data['seller']}'
to: '{item_data['bidder']}'
            """

            await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='Markdown')
            print(f"✅ Sent ItemSold notification for Token #{item_data['tokenId']}: {tx_hash}")

        except Exception as e:
            print(f"❌ Error sending ItemSold notification: {e}")

    async def send_bid_accepted_notification(self, bid_data, tx_hash, gas_used, gas_cost_hype, block_number):
        """Send notification for BidAccepted events"""
        try:
            price_hype = web3.from_wei(bid_data['pricePerItem'], 'ether')

            message = f"""
PiP & Friends {', '.join(map(str, bid_data['tokenId'])) if bid_data['tokenId'] else 'Unknown'} was bought for {price_hype:.6f} HYPE

from: '{bid_data['seller']}'
to: '{bid_data['bidder']}'
            """

            await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='Markdown')
            print(f"✅ Sent BidAccepted notification for Token #{bid_data['tokenId']}: {tx_hash}")

        except Exception as e:
            print(f"❌ Error sending BidAccepted notification: {e}")

    async def send_generic_notification(self, token_ids, buyer, seller, tx_value_hype, tx_hash, gas_used, gas_cost_hype,
                                        block_number):
        """Send generic notification for other NFT transactions"""
        try:
            message = f"""
PiP & Friends {', '.join(map(str, token_ids)) if token_ids else 'Unknown'} was bought for {tx_value_hype:.6f} HYPE

from: '{seller}'
to: '{buyer}'
            """

            await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='Markdown')
            print(f"✅ Sent generic notification: {tx_hash}")

        except Exception as e:
            print(f"❌ Error sending generic notification: {e}")

    async def determine_transaction_type(self, tx, receipt, event_details=None):
        """Enhanced transaction type determination with event detection"""
        try:
            # Check for specific events first
            if event_details:
                for event_type, _ in event_details:
                    if event_type == "ItemSold":
                        return "buyItems"
                    elif event_type == "BidAccepted":
                        return "acceptBids"

            # Fallback to function selector analysis
            if tx.input and len(tx.input) >= 10:
                function_selector = tx.input[:10]

                if function_selector in ['0x8b3f8b2a', '0x12345678']:
                    return "buyItems"
                elif function_selector in ['0x9b3f8b2a', '0x87654321']:
                    return "acceptBids"

            # Final fallback heuristic
            if tx.value > 0:
                return "buyItems"
            else:
                return "acceptBids"

        except Exception as e:
            print(f"❌ Error determining transaction type: {e}")

        return "unknown"


# Connection verification function
async def verify_hyperevm_connection():
    """Verify connection to HyperEVM"""
    try:
        if web3.is_connected():
            chain_id = web3.eth.chain_id
            latest_block = web3.eth.block_number

            print(f"✅ Connected to HyperEVM successfully!")
            print(f"🔗 Chain ID: {chain_id}")
            print(f"📊 Latest block: {latest_block}")
            print(f"🌐 RPC URL: {HYPEREVM_RPC}")

            return True
        else:
            print("❌ Failed to connect to HyperEVM")
            return False

    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False


# Main execution
async def main():
    print("🚀 Initializing HyperEVM NFT Tracker...")
    print(f"📍 Target Contract: {CONTRACT_ADDRESS}")

    # Verify HyperEVM connection
    if not await verify_hyperevm_connection():
        print("❌ Cannot proceed without HyperEVM connection")
        return

    # Initialize and start tracker
    tracker = HyperEVMNFTTracker()
    await tracker.track_transactions()


if __name__ == "__main__":
    asyncio.run(main())
