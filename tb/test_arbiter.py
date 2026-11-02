
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer, RisingEdge, ClockCycles


@cocotb.test()
async def test_reset(dut):
    clock = Clock(dut.clk, 10, unit="ns")
    clock.start()

    dut.rst_n.value = 0
    dut.req.value = 0
    dut.ready.value = 0

    await ClockCycles(dut.clk, 2)

    dut.rst_n.value = 1
    dut.req.value = 0b1111

    await Timer(1, unit="ns")

    assert int(dut.grant.value) == 0b0001

@cocotb.test()
async def test_round_robin_rotation(dut):
    clock = Clock(dut.clk, 10, unit="ns")
    clock.start()

    # Reset
    dut.rst_n.value = 0
    dut.req.value = 0
    dut.ready.value = 0

    await ClockCycles(dut.clk, 2)

    dut.rst_n.value = 1
    dut.req.value = 0b1111

    await Timer(1, unit="ns")

    # Verify initial priority
    assert int(dut.grant.value) == 0b0001

    # Enable transfers
    dut.ready.value = 1

    expected_grants = [0b0010, 0b0100, 0b1000, 0b0001] * 5

    for expected in expected_grants:
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")

        assert int(dut.grant.value) == expected, (
        f"Expected {expected:04b}, "
        f"got {int(dut.grant.value):04b}"
    )

@cocotb.test()
async def test_backpressure(dut):
    clock = Clock(dut.clk, 10, unit="ns")
    clock.start()

    dut.rst_n.value = 0
    dut.req.value = 0
    dut.ready.value = 0

    await ClockCycles(dut.clk, 2)

    dut.rst_n.value = 1
    dut.req.value = 0b1111

    await Timer(1, unit="ns")

    assert int(dut.grant.value) == 0b0001

    for i in range(5):
        await ClockCycles(dut.clk, 1)
        await Timer(1, unit="ns")

        assert int(dut.grant.value) == 0b0001

    dut.ready.value = 1

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")

    assert int(dut.grant.value) == 0b0010

    dut.ready.value = 0

    for i in range(3):
        await ClockCycles(dut.clk, 1)
        await Timer(1, unit="ns")

        assert int(dut.grant.value) == 0b0010

@cocotb.test()
async def test_sparse_requests(dut):
    clock = Clock(dut.clk, 10, unit="ns")
    clock.start()

    dut.rst_n.value = 0
    dut.req.value = 0
    dut.ready.value = 0

    await ClockCycles(dut.clk, 2)

    dut.rst_n.value = 1
    dut.req.value = 0b1010

    await Timer(1, unit="ns")

    assert int(dut.grant.value) == 0b0010

    dut.ready.value = 1

    expected_grants = [0b1000, 0b0010] * 5

    for expected in expected_grants:
        await ClockCycles(dut.clk, 1)
        await Timer(1, unit="ns")

        assert int(dut.grant.value) == expected, (
            f"expected {expected:04b}, "
            f"got {int(dut.grant.value):04b}"
        )

    dut.ready.value = 0
    dut.rst_n.value = 0
    dut.req.value = 0

    await ClockCycles(dut.clk, 2)

    dut.rst_n.value = 1

    # Test a different sparse request pattern
    dut.req.value = 0b0101

    await Timer(1, unit="ns")

    assert int(dut.grant.value) == 0b0001

    dut.ready.value = 1

    expected_grants = [0b0100, 0b0001] * 2

    for expected in expected_grants:
        await ClockCycles(dut.clk, 1)
        await Timer(1, unit="ns")
    
        assert int(dut.grant.value) == expected, (
            f"expected {expected:04b}, "
            f"got {int(dut.grant.value):04b}"
        )

@cocotb.test()
async def test_dynamic_requests(dut):
    clock = Clock(dut.clk, 10, unit="ns")
    clock.start()

    dut.rst_n.value = 0
    dut.req.value = 0
    dut.ready.value = 0

    await ClockCycles(dut.clk, 2)

    dut.rst_n.value = 1
    dut.req.value = 0b1111

    await Timer(1, unit="ns")
    assert int(dut.grant.value) == 0b0001

    dut.ready.value = 1

    # Accept R0
    await ClockCycles(dut.clk, 1)
    await Timer(1, unit="ns")
    assert int(dut.grant.value) == 0b0010

    # R0 and R1 stop requesting
    dut.req.value = 0b1100
    await Timer(1, unit="ns")


    assert int(dut.grant.value) == 0b0100

    await ClockCycles(dut.clk, 1)
    await Timer(1, unit="ns")

    assert int(dut.grant.value) == 0b1000

    dut.req.value = 0b0011
    await Timer(1, unit="ns")

    assert int(dut.grant.value) == 0b0001

    await ClockCycles(dut.clk, 1)
    await Timer(1, unit="ns")

    assert int(dut.grant.value) == 0b0010
