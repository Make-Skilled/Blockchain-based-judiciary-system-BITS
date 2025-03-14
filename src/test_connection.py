from web3 import Web3

def test_ganache_connection():
    # Connect to Ganache
    w3 = Web3(Web3.HTTPProvider('http://127.0.0.1:7545'))
    
    # Test connection
    if w3.isConnected():
        print("Successfully connected to Ganache!")
        print(f"Network ID: {w3.net.version}")
        
        # Get admin account
        admin_account = w3.eth.accounts[0]
        balance = w3.eth.get_balance(admin_account)
        balance_eth = w3.from_wei(balance, 'ether')
        
        print(f"\nAdmin Account: {admin_account}")
        print(f"Balance: {balance_eth} ETH")
        
        # Get network info
        gas_price = w3.eth.gas_price
        print(f"\nGas Price: {gas_price}")
        print(f"Latest Block: {w3.eth.block_number}")
        
    else:
        print("Failed to connect to Ganache!")

if __name__ == "__main__":
    test_ganache_connection() 