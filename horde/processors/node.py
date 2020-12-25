import argparse
import os
from typing import Dict, Any

from horde.processors.router import Router, processor


PUB_KET_EXT = '.pub.key'

@processor
class NodeProcessor(Router):
    public_key: bytes
    public_keys: Dict[str, bytes]
    private_key: bytes

    def __init__(self, config: Any, full_config: Any, args: argparse.Namespace):
        super().__init__(config, full_config, args)
        with open(os.path.join(self.config['root'], 'private.key'), 'rb') as f:
            self.private_key = f.read()
        files = [filename for filename in os.listdir(full_config['public_root'])
                 if filename.endswith(PUB_KET_EXT)]
        self.public_keys = {}
        for file in files:
            with open(os.path.join(full_config['public_root'], file), 'rb') as f:
                self.public_keys[file[:-len(PUB_KET_EXT)]] = f.read()
        self.public_key = self.public_keys[self.config['id']]
