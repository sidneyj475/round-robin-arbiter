from pathlib import Path
from cocotb_tools.runner import get_runner

root = Path(__file__).resolve().parent

runner = get_runner("verilator")

runner.build(
    sources=list((root / "rtl").glob("*.sv")),
    hdl_toplevel="round_robin_arbiter",
    build_dir=str(root / "sim_build"),
    always=True,
)

runner.test(
    hdl_toplevel="round_robin_arbiter",
    test_module=["test_arbiter",
    ],
    test_dir=str(root / "tb"),
    
)