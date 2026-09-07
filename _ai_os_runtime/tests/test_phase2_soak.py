from run_phase2_soak import assess


def test_soak_requires_elapsed_time_no_failures_and_continuous_samples():
    samples = [{"epoch": n * 60, "ok": True, "active_leases": 0} for n in range(1441)]
    assert assess(samples[:-1])["status"] == "pending"
    assert assess(samples)["status"] == "passed"
    assert assess(samples)["active_workload_endurance_accepted"] is False
    interrupted = samples[:10] + samples[15:]
    assert assess(interrupted)["status"] == "failed"
    samples[3]["ok"] = False
    assert assess(samples)["status"] == "failed"
