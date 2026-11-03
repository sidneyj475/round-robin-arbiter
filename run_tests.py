from pathlib import Path
from cocotb_tools.runner import get_runner

root = Path(__file__).resolve().parent

for n in [1, 2, 4, 8]:
    print(f"\n{'=' * 40}")
    print(f"Testing arbiter with N={n}")
    print(f"{'=' * 40}")
          
    runner = get_runner("verilator")

    runner.build(
        sources=[
            *sorted((root / "rtl").glob("*.sv")),
            root / "tb" / "arbiter_assertions.sv",
            root / "tb" / "arbiter_bind.sv",
        ],
        hdl_toplevel="round_robin_arbiter",
        build_dir=str(root / f"sim_build/n{n}"),
        build_args=[f"-GN={n}", "--assert",],
        always=True,
    )

    runner.test(
        hdl_toplevel="round_robin_arbiter",
        test_module=["test_arbiter"],
        test_dir=str(root / "tb"),
        
    )