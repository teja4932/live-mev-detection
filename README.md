# Live MEV Detector

Tools for monitoring Ethereum transactions and evaluating MEV detection performance, with a Foundry smart-contract project under `foundry-project/`.

## Configuration

Copy `.env.example` to `.env` and set `ALCHEMY_WS_URL` to your own Alchemy WebSocket endpoint.

## Python setup

Create and activate a virtual environment, then install the dependencies required by the monitoring scripts.

## Foundry project

```bash
cd foundry-project
forge build
forge test
```
