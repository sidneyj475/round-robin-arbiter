
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

    grant_counts = [0] * n

    idle_count = 0
    backpressure_count = 0
    accepted_count = 0

    accepted_grant_counts = [0] * n

    seen_requests = set()

    for cycle in range(1000):

        await FallingEdge(dut.clk)

        req = rng.randrange(1 << n)
        ready = rng.randrange(2)

        seen_requests.add(req)

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

        if actual_grant != 0:
            granted_index = actual_grant.bit_length() - 1
            grant_counts[granted_index] += 1

        if req == 0:
            idle_count += 1

        if actual_grant != 0 and ready == 0:
            backpressure_count += 1

        if actual_grant != 0 and ready == 1:
            accepted_count += 1
            granted_index = actual_grant.bit_length() - 1
            accepted_grant_counts[granted_index] += 1

        await RisingEdge(dut.clk)
        model.update(actual_grant, ready)

    dut._log.info(f"Grant coverage (N={n}): {grant_counts}")

    assert all(count > 0 for count in grant_counts), (
    f"Not all requesters were granted: {grant_counts}"
    )

    dut._log.info(
        f"N={n}: idle={idle_count}, "
        f"backpressure={backpressure_count}, "
        f"accepted={accepted_count}"
    )

    assert idle_count > 0
    assert backpressure_count > 0
    assert accepted_count > 0
    assert all(count > 0 for count in accepted_grant_counts)

    dut._log.info(
        f"Request patterns covered: {len(seen_requests)}/{1 << n}"
    )

@cocotb.test()
async def test_mid_operation_reset(dut):
    n = len(dut.req)
    all_requests = (1 << n) - 1

    clock = Clock(dut.clk, 10, unit="ns")
    clock.start()

    # Initial reset
    dut.rst_n.value = 0
    dut.req.value = 0
    dut.ready.value = 0

    await ClockCycles(dut.clk, 2)

    dut.rst_n.value = 1
    dut.req.value = all_requests
    dut.ready.value = 1

    await Timer(1, unit="ns")

    # Initial priority must be R0
    assert int(dut.grant.value) == 1

    # Accept one transaction
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")

    expected = 1 << (1 % n)

    assert int(dut.grant.value) == expected, (
        f"N={n}: expected {expected:0{n}b} "
        f"after first transfer, "
        f"got {int(dut.grant.value):0{n}b}"
    )

    # Assert asynchronous reset between clock edges
    await FallingEdge(dut.clk)

    dut.rst_n.value = 0
    dut.ready.value = 0

    # Check reset before the next rising edge
    await Timer(1, unit="ns")

    assert int(dut.grant.value) == 1, (
        f"N={n}: priority did not reset to R0"
    )

    # Deassert reset
    dut.rst_n.value = 1

    await Timer(1, unit="ns")

    assert int(dut.grant.value) == 1, (
        f"N={n}: initial priority not preserved "
        f"after reset release"
    )

    # Resume normal arbitration
    dut.ready.value = 1

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")

    assert int(dut.grant.value) == expected, (
        f"N={n}: rotation did not resume "
        f"correctly after reset"
    )

@cocotb.test()
async def test_fairness_no_starvation(dut):
    n = len(dut.req)
    all_requests = (1 << n) - 1
    rounds = 20

    clock = Clock(dut.clk, 10, unit="ns")
    clock.start()

    # Reset the arbiter
    dut.rst_n.value = 0
    dut.req.value = 0
    dut.ready.value = 0

    await ClockCycles(dut.clk, 2)

    # Begin continuous contention
    await FallingEdge(dut.clk)

    dut.rst_n.value = 1
    dut.req.value = all_requests
    dut.ready.value = 1

    await Timer(1, unit="ns")

    grant_counts = [0] * n

    # Each requester should win once per round
    for transaction in range(n * rounds):
        expected_index = transaction % n
        expected_grant = 1 << expected_index

        actual_grant = int(dut.grant.value)

        assert actual_grant == expected_grant, (
            f"N={n}, transaction={transaction}: "
            f"expected={expected_grant:0{n}b}, "
            f"got={actual_grant:0{n}b}"
        )

        grant_counts[expected_index] += 1

        # Accept current grant
        await RisingEdge(dut.clk)

        # Allow registered priority to update
        await Timer(1, unit="ns")

    # Every requester must receive exactly 20 grants
    assert all(count == rounds for count in grant_counts), (
        f"N={n}: unfair arbitration: {grant_counts}"
    )

    dut._log.info(
        f"N={n}: fairness verified over "
        f"{n * rounds} accepted transfers. "
        f"Grant counts: {grant_counts}"
    )

