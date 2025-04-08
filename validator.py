#!/usr/bin/env python

import argparse
import numpy as np
import time
import bittensor as bt

# Compute the spec version from __version__.
__version__ = "2.0.12"
version_split = __version__.split(".")
spec_version = (1000 * int(version_split[0])) + (10 * int(version_split[1])) + (1 * int(version_split[2]))

config = bt.Config()
config.logging = bt.Config()
config.logging.debug = True
bt.logging(config=config, logging_dir=config.logging.logging_dir)

bt.logging.info(f"spec_version: {spec_version}")

def parse_args():
    parser = argparse.ArgumentParser(description="Validator script for Bittensor")
    parser.add_argument("--netuid", type=int, default=31, help="Subnet netuid")
    parser.add_argument("--wallet.name", type=str, required=True, help="Wallet coldkey name")
    parser.add_argument("--wallet.hotkey", type=str, required=True, help="Wallet hotkey name")
    return parser.parse_args()

def check_registered(st, netuid, wallet, metagraph):
    # Check if the wallet's hotkey is registered on the given netuid.
    if not st.is_hotkey_registered(netuid=netuid, hotkey_ss58=wallet.hotkey.ss58_address):
        print(f"Wallet: {wallet} is not registered on netuid {netuid}. "
              f"Please register the hotkey using `btcli subnets register` before trying again.")
        exit()
    else:
        uid = metagraph.hotkeys.index(wallet.hotkey.ss58_address)
        print(f"Wallet: {wallet} is registered with uid: {uid}.")

def main():
    args = parse_args()

    # Create a configuration and override defaults with command-line arguments.
    config = bt.Config()
    config.netuid = args.netuid

    config.wallet = bt.Config()
    config.wallet.name = args.__dict__["wallet.name"]
    config.wallet.hotkey = args.__dict__["wallet.hotkey"]

    # Initialize the wallet, subtensor, and metagraph objects.
    wallet = bt.wallet(config=config.wallet)
    bt.logging.info(f"Initialized wallet: {wallet}")
    subtensor = bt.subtensor()
    metagraph = subtensor.metagraph(config.netuid)

    last_epoch_block = subtensor.get_current_block()
    bt.logging.info(f"Last epoch block: {last_epoch_block}")

    check_registered(subtensor, config.netuid, wallet, metagraph)

    # Initialize last_successful_block as the current block.
    last_successful_block = subtensor.get_current_block()-200
    bt.logging.info(f"Initial last_successful_block: {last_successful_block}")

    # Infinite loop: update weights when block difference is >= 100.
    while True:
        current_block = subtensor.get_current_block()
        block_diff = current_block - last_successful_block

        if block_diff >= 200:
            bt.logging.info(f"Block diff {block_diff} >= 200. Attempting to set weights.")

            # Recalculate weights: hardcode weight 1 for uid 0; rest are 0.
            raw_weight_uids = metagraph.uids
            raw_weights = np.zeros(raw_weight_uids.shape, dtype=np.float32)
            raw_weights[raw_weight_uids == 251] = 1.0

            bt.logging.info(f"raw_weights: {raw_weights}")
            bt.logging.info(f"raw_weight_uids: {raw_weight_uids}")

            processed_weight_uids, processed_weights = bt.utils.weight_utils.process_weights_for_netuid(
                uids=raw_weight_uids,
                weights=raw_weights,
                netuid=config.netuid,
                subtensor=subtensor,
                metagraph=metagraph,
            )
            bt.logging.info(f"processed_weights: {processed_weights}")
            bt.logging.info(f"processed_weight_uids: {processed_weight_uids}")

            uint_uids, uint_weights = bt.utils.weight_utils.convert_weights_and_uids_for_emit(
                uids=processed_weight_uids,
                weights=processed_weights
            )
            bt.logging.info(f"uint_weights: {uint_weights}")
            bt.logging.info(f"uint_uids: {uint_uids}")

            try:
                result, msg = subtensor.set_weights(
                    wallet=wallet,
                    netuid=config.netuid,
                    uids=uint_uids,
                    weights=uint_weights,
                    wait_for_finalization=False,
                    wait_for_inclusion=False,
                    version_key=spec_version,
                )
                if result:
                    bt.logging.info("set_weights on chain successfully!")
                    last_successful_block = current_block
                else:
                    bt.logging.info(f"set_weights failed: {msg}")
            except Exception as e:
                bt.logging.info(f"An exception occurred during set_weights: {str(e)}")
        else:
            bt.logging.info(f"Block diff {block_diff} < 200. Waiting. "
                            f"Current block: {current_block}, Last successful block: {last_successful_block}")
        time.sleep(10)

if __name__ == "__main__":
    main()
