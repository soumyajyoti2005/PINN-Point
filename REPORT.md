# PINNpoint ML Baseline Diagnostics & Early Detection Report (Stage 9 / 10a)

## PART A: Diagnostics (none-class bug & Label Checks)
1. **none-class bug**:
   - The bug was an index mismatch. The `LightGBM` multi-class classifier aligns its classes alphanumerically if not explicitly guided, meaning the index of `none` could differ from training to evaluation.
   - After explicit alignment, the predicted-class histogram on the 100 test baseline runs shows exactly 100 predictions of `none`. The mean predicted probability of `none` on baseline runs is > 90%.
   - **Finding**: The baseline false alarm rate is genuinely 0.00% (0/100) on the raw model. The `none` class bug is resolved.

2. **Unseen Pipe Leakage**:
   - No `test_unseen_pipe` pipe_id appears in any train/val label. 
   - **Finding**: The 0.00% top-5 accuracy on unseen pipes is genuine because a multi-class classification model cannot output a class index that it has never seen during training. It treats classification as a categorical choice, not a continuous coordinate.

3. **Docker Compose Commands**:
   - Tests: `docker compose run --rm sim pytest tests/test_ml.py -v`
   - Training: `docker compose run --rm -e DATASET_NAME=large1000 -v "c:\projects\PINN-Point\backend:/app" sim python -m app.ml.train`
   - Evaluation: `docker compose run --rm -e DATASET_NAME=large1000 -v "c:\projects\PINN-Point\backend:/app" sim python -m app.ml.evaluate`
   - Dataset Gen: `docker compose run --rm sim python app/sim/generate_dataset.py`

## PART B: Leakage and Honesty Checks
1. **Shuffled-label Control**:
   - Accuracy collapses to random guess when labels are shuffled, proving the model is genuinely learning from the features, not exploiting a trivial data leak.
2. **Mismatched-expected Control**:
   - When evaluating with a mismatched baseline (using a different storm), the residual model accuracy completely collapses.
   - **Finding**: This validates that the baseline subtraction is critical. The residual features are highly sensitive to the exact rainfall curve.

3. **B5. Threshold Table (Residual Model)**
   - Threshold 0.2: Base FA 5.0%, Det-Act Top-1 83.6%, Det-Act Flagged 92.8%
   - Threshold 0.3: Base FA 4.0%, Det-Act Top-1 75.5%, Det-Act Flagged 78.5%
   - Threshold 0.4: Base FA 2.0%, Det-Act Top-1 70.4%, Det-Act Flagged 72.4%
   - Threshold 0.5: Base FA 2.0%, Det-Act Top-1 65.3%, Det-Act Flagged 67.3%
   - Threshold 0.6: Base FA 0.0%, Det-Act Top-1 59.1%, Det-Act Flagged 59.1%
   - **Finding**: A threshold around 0.5 gives a good tradeoff: ~2% False Alarm rate while successfully flagging ~67% of detectable blockages.

4. **B6. Residual Decay (Severity 0.3)**
   - Hop 0 (Upstream of blockage): 0.0543 m
   - Hop 1: 0.0579 m
   - Hop 2: 0.0546 m
   - Hop 3+: 0.0499 m
   - **Finding**: Residuals at severity 0.3 are extremely small (all ~5 cm) and decay slightly as you move further away, but are generally too small to be separated from noise for low-severity blockages.

## PART C: Early Detection
Rain bounds: Peak (4/24/71 min), Ends (19/53/89 min).
The unified early-detection model was trained with cutoffs: 15, 30, 45, 60, 90, 120 minutes.

### Performance by Cutoff (Detectable + Active Upstream N=98)
| Cutoff | Top-1 | Top-3 | Top-5 | Baseline FA (>=0.3) |
|---|---|---|---|---|
| **15 mins** | 24.5% | 46.9% | 53.1% | 2.0% |
| **30 mins** | 70.4% | 88.8% | 90.8% | 0.0% |
| **45 mins** | 79.6% | 94.9% | 95.9% | 1.0% |
| **60 mins** | 80.6% | 95.9% | 96.9% | 2.0% |
| **90 mins** | 75.5% | 94.9% | 96.9% | 3.0% |
| **120 mins**| 73.5% | 91.8% | 93.9% | 5.0% |

- **Finding**: Early detection is highly effective. Accuracy peaks at the **45-60 minute mark**, which coincides with the time after the median rain ends and all transient peaks have flowed through the system. Waiting 120 minutes slightly degrades performance or increases False Alarms due to noise accumulating with no new signal.

## PART D: Timing
- CPU count: 12
- Execution of `run_simulation` in a single process: `0.1192s ± 0.0195s` per run.
- **Finding**: Swapping the disk-based I/O to purely in-memory string-based I/O for `inp_text` yields extreme performance. We can easily run ~10 concurrent simulations per second on a single core.
