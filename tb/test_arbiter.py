
import cocotb, random
from cocotb.clock import Clock
from cocotb.triggers import Timer, RisingEdge, ClockCycles, FallingEdge
from arbiter_model import ArbiterModel


@cocotb.test()
async def test_reset(dut):
    n = len(dut.req)

    clock = Clock(dut.clk, 10, unit="ns")
    clock.start()

    dut.rst_n.value = 0
    dut.req.value = 0
    dut.ready.value = 0

    await ClockCycles(dut.clk, 2)

    dut.rst_n.value = 1
    dut.req.value = (1 << n) - 1

    await Timer(1, unit="ns")

    assert int(dut.grant.value) == 0b0001

@cocotb.test()
async def test_round_robin_rotation(dut):
    n = len(dut.req)

    clock = Clock(dut.clk, 10, unit="ns")
    clock.start()

    # Reset
    dut.rst_n.value = 0
    dut.req.value = 0
    dut.ready.value = 0

    await ClockCycles(dut.clk, 2)

    dut.rst_n.value = 1
    dut.req.value = (1 << n) - 1

    await Timer(1, unit="ns")

    # Verify initial priority
    assert int(dut.grant.value) == 0b0001

    # Enable transfers
    dut.ready.value = 1

    expected_grants = [1 << ((i + 1) % n) for i in range(n)] * 5

    for expected in expected_grants:
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")

        assert int(dut.grant.value) == expected, (
        f"Expected {expected:04b}, "
        f"got {int(dut.grant.value):04b}"
    )

@cocotb.test()
async def test_backpressure(dut):
    n = len(dut.req)
    all_requests = (1 << n) - 1
    next_grant = 1 << (1 % n)

    clock = Clock(dut.clk, 10, unit="ns")
    clock.start()

    dut.rst_n.value = 0
    dut.req.value = 0
    dut.ready.value = 0

    await ClockCycles(dut.clk, 2)

    dut.rst_n.value = 1
    dut.req.value = all_requests

    await Timer(1, unit="ns")

    assert int(dut.grant.value) == 0b0001

    for i in range(5):
        await ClockCycles(dut.clk, 1)
        await Timer(1, unit="ns")

        assert int(dut.grant.value) == 0b0001

    dut.ready.value = 1

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")

    assert int(dut.grant.value) == next_grant

    dut.ready.value = 0

    for i in range(3):
        await ClockCycles(dut.clk, 1)
        await Timer(1, unit="ns")

        assert int(dut.grant.value) == next_grant

@cocotb.test()
async def test_sparse_requests(dut):
    n = len(dut.req)

    even_req = sum(1 << i for i in range(0, n, 2))
    odd_req = sum(1 << i for i in range(1, n, 2))

    clock = Clock(dut.clk, 10, unit="ns")
    clock.start()

    for req in [odd_req, even_req]:
        # Reset before each scenario
        dut.rst_n.value = 0
        dut.req.value = 0
        dut.ready.value = 0

        await ClockCycles(dut.clk, 2)

        dut.rst_n.value = 1
        dut.req.value = req

        await Timer(1, unit="ns")

        # Find all active requesters
        active_indices = [
            i for i in range(n)
            if req & (1 << i)
        ]

        # Check initial grant
        initial_grant = (
            1 << active_indices[0]
            if active_indices else 0
        )

        assert int(dut.grant.value) == initial_grant

        dut.ready.value = 1

        # Build expected grant sequence
        if active_indices:
            expected_grants = [
                1 << active_indices[(i + 1) % len(active_indices)]
                for i in range(len(active_indices))
            ] * 5
        else:
            expected_grants = [0] * 5

        # Verify rotation
        for expected in expected_grants:
            await ClockCycles(dut.clk, 1)
            await Timer(1, unit="ns")

            actual = int(dut.grant.value)

            assert actual == expected, (
                f"N={n}, req={req:0{n}b}, "
                f"expected={expected:0{n}b}, "
                f"got={actual:0{n}b}"
            )

@cocotb.test()
async def test_dynamic_requests(dut):
    n = len(dut.req)
    model = ArbiterModel(n)

    clock = Clock(dut.clk, 10, unit="ns")
    clock.start()

    dut.rst_n.value = 0
    dut.req.value = 0
    dut.ready.value = 0

    await ClockCycles(dut.clk, 2)
    dut.rst_n.value = 1

    all_requests = (1 << n) - 1

    patterns = [
        all_requests,
        all_requests,
        sum(1 << i for i in range(0, n, 2)),
        sum(1 << i for i in range(1, n, 2)),
        0,
        all_requests,
    ]

    for req in patterns:
        await FallingEdge(dut.clk)
        
        dut.req.value = req
        dut.ready.value = 1

        await Timer(1, unit="ns")
        
        expected = model.expected_grant(req)
        actual_grant = int(dut.grant.value)
        
        assert actual_grant == 0 or (actual_grant & (actual_grant - 1)) == 0
        assert (actual_grant & ~req) == 0
        
        assert actual_grant == expected, (
            f"N={n}, req={req:0{n}b}, "
            f"expected={expected:0{n}b}, "
            f"actual={actual_grant:0{n}b}"
        )

        await RisingEdge(dut.clk)
        model.update(actual_grant, 1)


@cocotb.test()
async def test_randomized(dut):
    clock = Clock(dut.clk, 10, unit="ns")
    clock.start()

    n = len(dut.req)
    model = ArbiterModel(n)

    dut.rst_n.value = 0
    dut.req.value = 0
    dut.ready.value = 0

    await ClockCycles(dut.clk, 2)
    dut.rst_n.value = 1

    rng = random.Random(42)

    for cycle in range(1000):
        await FallingEdge(dut.clk)

        req = rng.randrange(1 << n)
        ready = rng.randrange(2)

        dut.req.value = req
        dut.ready.value = ready

        await Timer(1, unit="ns")

        expected = model.expected_grant(req)
        actual_grant = int(dut.grant.value)

        assert actual_grant == 0 or (actual_grant & (actual_grant - 1)) == 0
        assert (actual_grant & ~req) == 0

        assert actual_grant == expected, (
            f"Cycle {cycle}: req={req:0{n}b}, "
            f"ready={ready}, expected={expected:0{n}b}, "
            f"got={actual_grant:0{n}b}"
        )

        await RisingEdge(dut.clk)
        model.update(actual_grant, ready)