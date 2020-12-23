# Horde Blockchain: A Simple 

## How to Run

```shell
# Prepare the environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# Use the default configuration file
cp config.example.yaml config.yaml
# Init keys and genesis block
python3 main.py init
# Start all the nodes, it will spawn multiple nodes and wait for them
python3 main.py start
```

Then you can open another shell, start a client and open a interactive webpage.

```shell
python3 main.py client --open
```

## Implementation Detail

See <https://github.com/sunziping2016/horde-blockchain/wiki>.
