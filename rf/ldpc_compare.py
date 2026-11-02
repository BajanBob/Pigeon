#!/usr/bin/env python3
"""
FEC coding-gain comparison: convolutional r=1/2 K=7 (soft Viterbi, the shipping
PigeonFSK-2 code) vs a rate-1/2 regular (3,6) LDPC with normalized min-sum.

Both codes are measured apples-to-apples on the SAME BPSK + AWGN channel, at the
same rate (1/2) and the same ~200 info bits per frame, so the delta in threshold
is the pure FEC gain you'd get by swapping the code in the waveform. (The FSK
front-end and its soft metrics are common to both, so the coding-gain delta
transfers to the over-the-air threshold.)
"""
import numpy as np
import pigeon_rf2 as rf          # reuse conv_encode + viterbi_soft (the real code)

rng = np.random.default_rng(12345)

# ----------------------------- LDPC construction -----------------------------
def make_regular_ldpc(n, dv=3, dc=6, seed=7):
    """Random regular (dv,dc) parity-check matrix H (m x n), m = n*dv/dc."""
    r = np.random.default_rng(seed)
    m = n * dv // dc
    # column-wise socket assignment (progressive, avoid duplicate edges)
    while True:
        H = np.zeros((m, n), np.int8)
        row_deg = np.zeros(m, int)
        ok = True
        for col in range(n):
            avail = np.where(row_deg < dc)[0]
            if len(avail) < dv:
                ok = False; break
            rows = r.choice(avail, size=dv, replace=False)
            H[rows, col] = 1; row_deg[rows] += 1
        if ok and row_deg.sum() == n * dv:
            return H

def gf2_systematic(H):
    """RREF over GF(2) with column pivoting. Returns (G, perm) so that with
    Hs = H[:,perm] = [P | I_m], the generator G = [I_k | P^T] satisfies G Hs^T = 0."""
    H = H.copy() % 2
    m, n = H.shape
    pivcols = []; row = 0
    for col in range(n):
        if row >= m: break
        piv = np.where(H[row:, col] == 1)[0]
        if len(piv) == 0: continue
        pr = row + piv[0]
        if pr != row: H[[row, pr]] = H[[pr, row]]
        for r in range(m):
            if r != row and H[r, col]: H[r] ^= H[row]
        pivcols.append(col); row += 1
    if len(pivcols) < m:
        return None, None                      # H not full rank
    noncols = [c for c in range(n) if c not in set(pivcols)]
    perm = np.array(noncols + pivcols)         # info columns first, parity (identity) last
    Hs = H[:, perm]                            # last m columns form I_m (RREF, pivot order)
    k = n - m
    P = Hs[:, :k]                              # m x k
    G = np.zeros((k, n), np.int8)
    G[:, :k] = np.eye(k, dtype=np.int8)
    G[:, k:] = P.T % 2
    return G, perm

def ldpc_encode(G, info):
    return (info @ G) % 2

def minsum_decode(llr, H, iters=40, alpha=0.8):
    """Normalized min-sum LDPC decoder. llr: channel LLRs (+ => bit 0)."""
    m, n = H.shape
    # edge lists
    rows = [np.where(H[i])[0] for i in range(m)]
    cols = [np.where(H[:, j])[0] for j in range(n)]
    M = {}                                   # messages var->check and check->var
    for i in range(m):
        for j in rows[i]:
            M[(i, j)] = llr[j]
    post = llr.copy()
    for _ in range(iters):
        # check -> var
        C = {}
        for i in range(m):
            js = rows[i]
            vals = np.array([M[(i, j)] for j in js])
            signs = np.sign(vals); signs[signs == 0] = 1
            abss = np.abs(vals)
            for idx, j in enumerate(js):
                others = np.delete(abss, idx)
                s = np.prod(np.delete(signs, idx))
                C[(i, j)] = alpha * s * np.min(others)
        # var -> check + posterior
        for j in range(n):
            isC = cols[j]
            tot = llr[j] + sum(C[(i, j)] for i in isC)
            post[j] = tot
            for i in isC:
                M[(i, j)] = tot - C[(i, j)]
        hard = (post < 0).astype(np.int8)
        if not np.any((H @ hard) % 2):
            return hard
    return (post < 0).astype(np.int8)

# ----------------------------- experiment -----------------------------
K_INFO = 204
N_LDPC = 408
Hmat = make_regular_ldpc(N_LDPC, 3, 6)
G, perm = gf2_systematic(Hmat)
assert G is not None, "LDPC systematic form failed"
Hp = Hmat[:, perm]                           # permuted H matches G
# sanity: G Hp^T == 0
assert not np.any((G @ Hp.T) % 2), "G/H mismatch"

def run_conv(ebn0_db, trials):
    ok = 0
    for _ in range(trials):
        info = rng.integers(0, 2, K_INFO).astype(np.int8)
        coded = rf.conv_encode(info)                 # rate 1/2 (+6 flush)
        Rc = len(info) / len(coded)
        sigma = np.sqrt(1 / (2 * Rc * 10 ** (ebn0_db / 10)))
        x = 1 - 2 * coded.astype(float)              # BPSK: bit0->+1
        y = x + rng.normal(0, sigma, len(x))
        r = 2 * y / sigma ** 2                       # soft value, + => coded bit 0 (matches exp map)
        dec = rf.viterbi_soft(r)
        ok += np.array_equal(dec[:K_INFO], info)
    return ok / trials

def run_ldpc(ebn0_db, trials):
    ok = 0
    Rc = K_INFO / N_LDPC
    for _ in range(trials):
        info = rng.integers(0, 2, K_INFO).astype(np.int8)
        cw = ldpc_encode(G, info)
        sigma = np.sqrt(1 / (2 * Rc * 10 ** (ebn0_db / 10)))
        x = 1 - 2 * cw.astype(float)
        y = x + rng.normal(0, sigma, len(x))
        llr = 2 * y / sigma ** 2
        dec = minsum_decode(llr, Hp, iters=40)
        ok += np.array_equal(dec[:K_INFO], info)     # systematic: first k are info
    return ok / trials

if __name__ == "__main__":
    import time; t0 = time.time()
    print("Rate-1/2 FEC, ~204 info bits, BPSK+AWGN, frame (codeword) success rate\n")
    print(f"{'Eb/N0':>6} | {'conv K=7':>10} | {'LDPC(3,6)':>10}")
    print("-" * 34)
    for ebn0 in [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]:
        c = run_conv(ebn0, 60)
        l = run_ldpc(ebn0, 60)
        print(f"{ebn0:>5}  | {100*c:>8.0f}%  | {100*l:>8.0f}%")
    print(f"\n[done in {time.time()-t0:.0f}s]")
