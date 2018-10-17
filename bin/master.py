#!/usr/bin/env python3
import zmq
import argparse
import random
import sys
import time
import json
import logging
from collections import deque
from IPython import embed

context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.bind("tcp://*:5556")

monitor_socket = context.socket(zmq.PULL)
monitor_socket.bind("tcp://*:5559")
time.sleep(1)

QUEUE_LEN = 3


def main(args, logger):
    active_ts = deque()
    while True:
        time.sleep(0.1)
        # Use a string to avoid any chance of FPE
        ts = str(time.time())
        active_ts.appendleft(ts)
        msg = json.dumps(
            {"timestamp": "{}".format(ts), "control": "RUN", "label": "good"}
        )
        socket.send_string(msg)

        logger.info("Master message sent: {}.".format(msg))
        # If we should have a finished image acquisition,
        # check for the signal from the image processor
        if len(active_ts) >= QUEUE_LEN:
            mon_msg = monitor_socket.recv_json()
            logger.info("Monitor message received: {}".format(mon_msg))
            rcvd_ts = mon_msg["timestamp"]
            label = mon_msg["label"]
            out_ts = active_ts.pop()
            if out_ts != rcvd_ts:
                logging.error(
                    "Timestamps mis-aligned: received {}, expected {}.".format(
                        rcvd_ts, out_ts
                    )
                )
                # Check if we somehow missed a monitor message, in which
                # case we should simply ditch the current item to be sorted
                if active_ts.count(ts) > 0:
                    logging.error(
                        "Received TS is active but not at end of queue."
                    )
                    label = "UNK"
                # Otherwise we likely received a stale TS
                else:
                    # raise ValueError("Received non-active TS: {}".format(rcvd_ts))
                    logging.error(
                        "Received ts not in active timestamps: {}".format(
                            rcvd_ts
                        )
                    )
                    label = "UNK"
            else:
                logging.info("Received correct ts: {}".format(rcvd_ts))
        else:
            logging.info(
                "Advancing empty element, queue len: {}".format(len(active_ts))
            )
            label = "UNK"
        # Command the sorting mechanism with the given class
        logging.info("Sending to {} output.".format(label))
        # Advance the sorting line and activate elevator
        logging.info("Adavancing line and activating elevator.")


def parse_args():

    parser = argparse.ArgumentParser(
        description="Grab camera images and forward to sink."
    )
    optional = parser._action_groups.pop()
    required = parser.add_argument_group("required arguments")
    optional.add_argument("--master_address", default="tcp://localhost:5556")
    optional.add_argument("--sink_address", default="tcp://localhost:5558")
    optional.add_argument("--log_level", default="DEBUG")
    parser._action_groups.append(optional)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    logger = logging.getLogger("master")
    numeric_level = getattr(logging, args.log_level.upper())
    if not isinstance(numeric_level, int):
        raise ValueError("Invalid log level: {}".format(args.log_level))
    try:
        import coloredlogs

        coloredlogs.install(level=numeric_level)
    except ImportError:
        logging.basicConfig(level=numeric_level)
    # logger.setLevel(numeric_level)
    logger.info("Starting main...")
    main(args, logger)