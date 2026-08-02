# /verify

Proof mode before `claim_done`.

1. `gk_verify` bundle with allowlisted commands on disk.
2. Hollow + fault_probe when applicable.
3. `gk_verify.exit` → `directive: pass` only with fresh evidence.
4. Then `gk_phase.claim_done`. Chat “tests passed” is not proof.
