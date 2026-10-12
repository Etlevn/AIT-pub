# AIT (AI Trading)

**Behavioral finance and market dynamics of LLM traders in an experimental stock market.**

Laboratory asset markets have shown that prices can leave a known fundamental value when traders form expectations and trade with one another. AIT is the computational market used to ask that question of language models. Each trader is an LLM. It receives the market rules, its portfolio, and the history so far, then returns limit orders, a price forecast, and the plans and insights it writes down. The market clears the orders into a price, settles cash, shares, dividends, and interest, and carries that state into the next period.

The same rules run in two compositions. In a single-model market every trader is one model. In a heterogeneous market several models share a fixed set of traders and clear against one another. A two-model market is that second composition with two model entries.

Each run records prices, volume, orders, holdings, wealth, forecasts, and the text the model produced. The record lines those objects up as:

```text
plans and insights → forecasts → orders → holdings and wealth → market price
```

Plans and insights are model-generated text. They are the trader’s stated account of the period, not a direct observation of an internal reasoning process. This repository runs the market, stores that record, and prepares it for analysis.

## Research question

Under the same cash, inventory, dividend, and clearing constraints:

1. Do different models state different plans and submit different forecasts and orders?
2. How do those differences appear in prices, volume, holdings, and wealth when one model trades alone, and when several models trade in the same market?

The market summaries measure how far prices move from fundamental value, how forecasts compare with later prices, and how dispersed those results are across repeated runs. A separate coding step scores plans and insights against a fixed list of behavioral-finance mechanisms. Those summaries and scores describe the record. They do not by themselves identify why a price path occurred.

## What the system does

- Runs a multi-period stock market whose price is formed from the traders’ own limit orders, then updates holdings, cash, dividends, and interest.
- Gives every trader the same prompt structure, portfolio state, and market history.
- Runs a single-model market, or a heterogeneous market in which several models are assigned to a fixed set of traders.
- Repeats full experiments in batch, with logs and a configuration snapshot for each run.
- Checks structured model output and repairs malformed JSON before it enters the order book. A failed model call can pause that trader and wait for a retry.
- Integrates prices, orders, holdings, forecasts, and model text into tables indexed by run, trader, and period.
- Summarizes price deviation from fundamental value, forecast error, and cross-run dispersion.
- Scores plans and insights for a fixed list of behavioral-finance mechanisms.

Experiment outputs, logs, and API keys are not part of the repository. Each run writes them locally.

## Market design

Default parameters live in `config.py` (`EXPERIMENT_CONFIG`) and in `init/prompt/experiment_conditions.json`.

| Parameter | Default | Role |
| --- | --- | --- |
| Initial cash | 100 | Cash each trader starts with |
| Initial shares | 4 | Shares each trader starts with |
| Terminal value | 14 | Cash paid per share after the last round |
| Interest rate | 5% | Interest credited on cash each round |
| Dividend | 0.4 or 1.0 | Low and high dividend per share |
| Dividend probability | 0.5 | Weight on the low dividend |
| Practice rounds | 3 | Rounds used to learn the market |
| Trading rounds | 20 | Formal rounds |

The trader prompt describes the dividend as a random draw of 0.4 or 1.0 each period, identical for every trader. Settlement in `pfl.py` credits the probability-weighted dividend each round (0.7 per share at the defaults), then credits interest on cash. After the last trading round, remaining shares are converted at the terminal value, not at the last market price.

Orders are limit orders and are not carried across periods. A trader cannot sell more shares than it holds or spend more cash than it has. `mkt.py` clears the book by searching for the price that maximizes traded volume. If several prices tie, it uses their average, rounded down. If the two sides do not cross, it sets the price to the bid–ask midpoint. If the book is empty or one-sided, the previous price stands.

## How a run proceeds

`main.py` executes practice rounds first when `practice_rounds` is greater than zero, then the formal rounds. Practice ends with a reflection step. That reflection is copied forward and shown to the same trader in the formal market.

Each round does the following:

1. Read the previous period’s plans, insights, reflection, market history, and portfolio.
2. Ask the assigned model for orders, forecasts, and updated plans and insights.
3. Validate the response and repair malformed JSON when `AUTO_JSON_FIX` is on.
4. Write the order book and clear a market price.
5. Update each trader’s shares, cash, dividend, and interest, and write the next period’s input files.

Round 0 is generated by `prep.py` from the experiment parameters. Later rounds read `exp/<run>/input/r<N-1>/` and write `exp/<run>/output/r<N>/`, `exp/<run>/market/`, and the next `input/` directory.

```text
Round 0 state (init/r0)
        │
        ▼
Prompt + model call (ord.py)
        │
        ▼
Structured output (output/rN/*.json)
        │
        ├── proc.py  → plans, insights, order book
        ├── mkt.py   → market/rN.csv and mkt.csv
        └── pfl.py   → next market.txt and portfolio.txt
```

## Requirements

Python 3.8 or newer.

```bash
pip install -r requirements.txt
```

The main dependencies are `edsl` (Expected Parrot), `pandas`, `numpy`, `python-dotenv`, `matplotlib`, `seaborn`, `scipy`, and `statsmodels`.

Create a `.env` file in the repository root. Set the key for the API mode you select in `config.py`. Do not commit this file.

```bash
OPENAI_API_KEY=your_openai_api_key_here
EXPECTED_PARROT_API_KEY=your_expected_parrot_api_key_here
DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

## Configuration

All experiment settings are in `config.py`.

### Market composition

`EXPERIMENT_MODE` is `"sgl"` or `"br"`.

- **Single model (`sgl`).** Every trader uses `SINGLE_MODEL_CONFIG`. `num_llms` is the number of traders. `service_name` is optional and is passed through to Expected Parrot when set (for example `deep_infra`, `google`, or `together`).
- **Battle Royale (`br`).** This is the heterogeneous market. Traders are split across `BATTLE_ROYALE_CONFIG["custom_models"]`. Two entries make a two-model market; more entries make a larger mix. The trader count is the sum of each model’s `count`. `assignment_strategy` is `sequential`, `random`, or `balanced`. The assignment is saved as `br_config.json` inside the run directory. A single-model run saves `sgl_config.json`.

### API mode

`API_CONFIG["api_mode"]` is one of:

- `expected_parrot` — models are called through Expected Parrot / EDSL
- `openai`
- `deepseek`

### Prompts and BAS mode

Shared prompt files live in `init/prompt/`. When `USE_BAS_MODE` is `True`, `experiment_start` and `order_forecast_end` are taken from `init/prompt/bas/` instead. The active filenames are `PROMPT_FILES_BAS` in `config.py`.

The `bas/` directory contains two families, `amp` (amplify) and `sup` (suppress), numbered 1 through 20. Each number is a pair:

- `experiment_start_amp_N.txt` with `order_forecast_end_amp_N.txt`
- `experiment_start_sup_N.txt` with `order_forecast_end_sup_N.txt`

Point both entries at the same family and number. `main.py` prints the two filenames it will load.

Set `USE_BAS_MODE` to `False` to use the standard files named in `PROMPT_FILES`.

### Other switches

- `AUTO_JSON_FIX` repairs JSON after each round and can keep a backup.
- `DEBUG_CONFIG["save_raw_responses"]` stores the raw model text before parsing.
- `batch.py` sets `NUM_RUNS`, the number of full experiments to launch in sequence.

Analysis and integration scripts read their own JSON configs. Replace the absolute paths in those files with the directory that holds your runs before using them.

## Running an experiment

From the repository root:

```bash
python main.py
```

One invocation creates a run directory under `exp/`, runs practice (if configured), then runs the formal market. Logs go to `log/`.

To repeat the same configuration:

```bash
python batch.py
```

`batch.py` stops the batch if a run exits with a non-zero status. A failed model call can also pause inside `ord.py` and wait for Enter before retrying that trader.

## Recorded data

A run directory contains:

| Path | Contents |
| --- | --- |
| `sgl_config.json` or `br_config.json` | Model assignment for the run |
| `input/rN/` | Plans, insights, reflection, market history, and portfolio shown to each trader |
| `output/rN/` | Model JSON: plans, insights, price forecasts, and submitted orders |
| `market/rN.csv` | Orders and executions for that round |
| `market/mkt.csv` | Price and volume by round |

`data_proc/` turns those files into tables. `all_integ.py` can run the three integrators together:

- `market_integ.py` parses market-history text into `_mkt.csv`
- `rx_integ.py` stacks per-round order files into `_rX.csv`
- `output_integ.py` parses model JSON into `_output.csv`

`integ_merger.py` concatenates those tables across runs. Set `market_type` to `sgl` or `br` so each row can be labeled with the model that traded it. Formal runs are those whose round files continue through at least round 20.

```bash
python data_proc/all_integ.py --config data_proc/all_integ_config.json
python data_proc/integ_merger.py --config data_proc/integ_merger_config.json
```

The individual integrators (`market_integ.py`, `rx_integ.py`, `output_integ.py`) use the matching `*_config.json` in the same directory.

## Analysis

The analysis reads the recorded chain after a run. `anal/` summarizes the market path. Point `anal/anal_config.json` at a directory of runs and set `fundamental_value` (14 under the default design).

```bash
python anal/anal.py --config anal/anal_config.json
python anal/rat.py --config anal/anal_config.json
python anal/rob.py --config anal/anal_config.json
```

- `anal.py` writes rounds, mean squared deviation of price from fundamental value, price amplitude, and cross-trader portfolio-value variance, plus price–volume plots.
- `rat.py` measures forecast error against realized prices: MSE, the error distribution, an unbiasedness t-test, and autocorrelation.
- `rob.py` reads `anal.csv` and reports the mean, standard deviation, coefficient of variation, and 95% confidence interval for MSE, amplitude, and portfolio-value variance.

`nlp/` reads integrated model output and asks a model to code plans and insights against a fixed mechanism list in `nlp/nlp_config.json` (including extrapolation versus anchoring, diagnostic expectations, herding, overconfidence, loss aversion, and others). `nlp_merge.py` combines result files. `nlp_miss.py` lists rows whose plan or insight JSON is missing.

```bash
python nlp/nlp_main.py --input path/to/sgl_output.csv --output path/to/nlp_out --config nlp/nlp_config.json
```

## Repository layout

```text
config.py            experiment, model, API, and prompt settings
main.py              practice rounds, reflection, and formal market
batch.py             repeated runs of main.py
br.py                heterogeneous model assignment
init.py              run directory and opening market file
prep.py              round-0 cash, shares, and blank plans
ord.py               prompts, model calls, and response handling
proc.py              plans, insights, and the raw order book
mkt.py               market clearing
pfl.py               holdings, cash, dividend, and interest
prompt.py            prompt assembly
valid.py             order constraints
json_fix.py          post-round JSON repair
utils.py             JSON extraction and reflection parsing
collect_ep_html.py   Expected Parrot HTML collection
init/prompt/         standard prompts and experiment conditions
init/prompt/bas/     amplify and suppress prompt pairs
anal/                price, forecast, and robustness summaries
data_proc/           parsers and cross-run merges
nlp/                 mechanism coding of plans and insights
```

`exp/`, `log/`, `init/r0/`, `init/prac/`, and `.env` are gitignored. They are created or filled in when you run the market.
