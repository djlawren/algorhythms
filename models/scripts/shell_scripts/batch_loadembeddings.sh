#!/bin/bash
#SBATCH --job-name=pytorch-geometric-load-embeddings
#SBATCH --account=siads699s23_class        # change to your account
#SBATCH --partition=largemem
#SBATCH --nodes=1                # node count, change as needed
#SBATCH --ntasks-per-node=1      # do not change, leave as 1 task per node
#SBATCH --cpus-per-task=8       # cpu-cores per task, change as needed
##SBATCH --gpu_cmode=shared
##SBATCH --gpus-per-node=2
#SBATCH --mem=1000G               # memory per node, change as needed
#SBATCH --time=02:00:00
#SBATCH --mail-type=NONE

# These modules are required. You may need to customize the module version
# depending on which cluster you are on.
module load python/3.10.4 pyarrow/8.0.0 cuda cudnn

mode="$1"
modelchoice="$2"
dataversion="$3"
hidden_size="$4"
percentilecutoff="$5"

python -u ../load_embeddings_from_model.py "$mode" "$modelchoice" "$dataversion" "$hidden_size" "$percentilecutoff" >> slurm-${SLURM_JOB_ID}.out 2>&1
