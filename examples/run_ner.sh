python3 run_cli.py train --task_name=token-classification \
                          --model_name=dmis-lab/biobert-v1.1 \
                          --dataset_name=ncbi_disease \
                          --output_dir=./outputs \
                          --lr=3e-5 \
                          --epochs=3 \
                          --max_length=128 \
                          --batch_size=16 \
                          --overwrite_output_dir \
                          --fp16