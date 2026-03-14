set -f

input_path=../IMO2025.json,../CMO2024.json,../CMO2025.json
# directory to dump results
output_dirname=xxx
# directory to maintain a pool of generated proofs for each evaluated problem
proof_pool_dirname=${output_dirname}/proof_pool

python main.py \
    --input_paths ${input_path} \
    --output_dirname ${output_dirname} \
    --proof_pool_dirname ${proof_pool_dirname} \
    --n_best_proofs_to_sample 32 \
    --n_proofs_to_refine 1 \
    --n_agg_trials 32 \
    --n_parallel_proof_gen 128 \
    --n_verification_per_proof 64 \
    --skip_meta_verification \
    --start_round 1 \
    --max_rounds 16

set +f
