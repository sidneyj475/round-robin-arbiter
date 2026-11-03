# Parameterized Round-Robin Arbiter

[![Arbiter Verification](https://github.com/sidneyj475/round-robin-arbiter/actions/workflows/verification.yml/badge.svg)](https://github.com/sidneyj475/round-robin-arbiter/actions/workflows/verification.yml)

A parameterized, mask-based round-robin arbiter in SystemVerilog, verified with cocotb, Python, Verilator, and SystemVerilog Assertions (SVA). The repo has an independent reference model, directed and randomized tests, a parameterized regression, and a GitHub Actions CI workflow.

## Architecture

Uses two copies of a combinational fixed-priority arbiter:

1. **Masked arbiter:** only sees the requests that the current priority mask allows.
2. **Unmasked arbiter:** sees every active request, and takes over (the wraparound case) when no masked requests are active.

Each one grants the lowest-index active request. The final grant is selected like so:

```systemverilog
assign masked_req = mask & req;
assign grant = (|masked_grant) ? masked_grant : unmasked_grant;
```

The mask only changes on a rising clock edge when a grant is accepted (`ready && |grant`), so while `ready` is low the current priority is held. The grant output itself is combinational and is **not** gated by `ready`.

Active-low asynchronous reset clears the mask. With the mask cleared, the unmasked arbiter picks the lowest-index active requester first.

### Interface

| Signal | Direction | Width | Description |
| --- | --- | --- | --- |
| `clk` | Input | 1 | Arbitration clock |
| `rst_n` | Input | 1 | Active-low asynchronous reset |
| `req` | Input | `N` | Request vector; bit `i` represents requester `i` |
| `ready` | Input | 1 | Indicates the selected grant can be accepted |
| `grant` | Output | `N` | One-hot-or-zero grant vector |

**Transfer rule:** A grant is accepted when `ready && |grant` is true at a rising clock edge. With no active requests, `grant` is zero. With any active request, the arbiter produces a grant even if `ready` is low.

### Example: Four Requesters

Say all four requesters keep requesting and `ready = 1`. Accepted grants rotate like this:

```text
req:     1111  1111  1111  1111  1111
 grant:  0001  0010  0100  1000  0001  ...
          R0    R1    R2    R3    R0
```

Each column is one arbitration decision following an accepted transfer. Under backpressure (`ready = 0`), the priority state doesn't advance.

## Verification Strategy

The tests are written in cocotb, which drives the inputs and checks the outputs, and they run on Verilator. A separate Python reference model (`tb/arbiter_model.py`) keeps track of the next-priority requester index and computes the expected grant independently. It uses a cyclic search rather than mirroring the RTL's mask-based logic.

The testbench compares the DUT's grants to the model, checks that every grant is legal, and covers both directed scenarios and randomized traffic.

### Directed Tests

| Test | What it checks |
| --- | --- |
| `test_reset` | Initial arbitration priority after reset |
| `test_round_robin_rotation` | Priority rotates across continuously active requesters |
| `test_backpressure` | Priority doesn't advance while `ready = 0` |
| `test_sparse_requests` | Arbitration skips inactive requesters |
| `test_dynamic_requests` | DUT matches the reference model as request patterns change |
| `test_mid_operation_reset` | Asynchronous reset restores the initial priority during operation |
| `test_fairness_no_starvation` | Equal service under continuous contention and accepted transfers |

The fairness test keeps every request active and accepts `20 × N` transfers, then checks that each requester got exactly 20 grants.

### Randomized Verification

`test_randomized` runs 1,000 pseudorandom cycles per parameter configuration. The seed is fixed (`42`), so every run is identical. Each cycle randomizes:

- The `N`-bit request vector
- The `ready` input

On every cycle, the testbench checks the grant against the Python reference model and makes sure it's one-hot-or-zero and goes to an active requester.

It also keeps a few simple coverage counters:

- Grants observed per requester
- Accepted grants per requester
- Idle cycles (no requests)
- Backpressure cycles (grant present, `ready = 0`)
- Accepted transfers
- Distinct request patterns exercised

These are just testbench counters. They are **not** a claim of exhaustive functional coverage or formal verification.

### SystemVerilog Assertions

The assertions are in `tb/arbiter_assertions.sv` and get attached to the DUT through `bind` in `tb/arbiter_bind.sv`.

| Assertion | Property checked |
| --- | --- |
| `ap_onehot` | Grant is one-hot or zero |
| `ap_grant_valid` | Every asserted grant bit corresponds to an active request |
| `ap_no_request` | No request implies no grant |
| `ap_request_serviced` | At least one request implies a nonzero grant |

They're disabled during active-low reset and enabled in Verilator with `--assert`.

**Assertion validation:** I deliberately triggered an assertion violation locally to confirm that Verilator reports the failure and terminates the simulation. That fault was only for validation and isn't part of the normal regression.

## Parameterized Regression

The regression covers four configurations:

| Parameter | Requesters | Randomized cycles | Fairness-test accepted transfers |
| --- | ---: | ---: | ---: |
| `N=1` | 1 | 1,000 | 20 |
| `N=2` | 2 | 1,000 | 40 |
| `N=4` | 4 | 1,000 | 80 |
| `N=8` | 8 | 1,000 | 160 |

Each one runs the full cocotb test module with SVA enabled. The badge at the top reflects the status of the automated workflow.

## Repository Structure

```text
round-robin-arbiter/
├── rtl/
│   ├── priority_arbiter.sv       # Fixed-priority selection
│   └── round_robin_arbiter.sv    # Mask-based round-robin arbitration
├── tb/
│   ├── arbiter_model.py          # Independent Python reference model
│   ├── test_arbiter.py           # cocotb directed and randomized tests
│   ├── arbiter_assertions.sv     # SVA checks
│   └── arbiter_bind.sv           # Bind assertions to DUT
├── .github/
│   └── workflows/
│       └── verification.yml     # Automated verification regression
├── run_tests.py                 # Parameterized cocotb/Verilator runner
└── README.md
```

## Running the Regression Locally

### Prerequisites

- Python 3.14 (the version used in CI)
- cocotb 2.1.0
- Verilator 5.052 (the version used in CI)
- A C++ compiler and standard build tools

CI runs on Ubuntu 24.04 and builds Verilator 5.052 from source. Other compatible setups may work too, but the versions above are what CI tests.

### Setup

From the repo root, create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install 'cocotb==2.1.0'
```

Then check that Verilator is installed and on your `PATH`:

```bash
verilator --version
```

### Run the Tests

```bash
python run_tests.py
```

The runner builds and tests the design with `N=1`, `N=2`, `N=4`, and `N=8`, passing `--assert` to turn on the bound SVA checks. Build output goes under `sim_build/n1`, `sim_build/n2`, `sim_build/n4`, and `sim_build/n8`.

## Continuous Integration

The GitHub Actions workflow (`.github/workflows/verification.yml`) runs on every push and pull request. It:

1. Checks out the repository and sets up Python 3.14.
2. Restores a cached Verilator 5.052 installation if one is available.
3. Builds Verilator from source on a cache miss.
4. Installs cocotb 2.1.0.
5. Runs the full parameterized regression with SVA enabled.

Caching means Verilator itself isn't recompiled on every run. The simulation models are still rebuilt, so RTL changes always get tested.

## Scope and Limitations

This project is simulation-based RTL verification of arbitration behavior. The tests cover reset, rotation, backpressure, sparse and changing requests, randomized inputs, and fairness under continuous contention. That's not an exhaustive proof over every possible input sequence, and there's no claim about physical implementation or timing closure.
