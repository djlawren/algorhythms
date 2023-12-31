"""
This script is intended to generate embeddings on the entire data object using a model artefact
Prompt 1 (required) : mode of training, which could be 'distributedGPU', 'distributedCPU' or 'non-distributed'
Prompt 2 (required) : Name of model*.pkl file, from '/saved_files/model_artefacts' to use for training.
Prompt 3 (required) : Name of 'version' folder, from '/saved_files/data_representations' to use for training.
Prompt 4 (required) : Hidden layer size of model.pkl file
Prompt 5 (optional) : Percentile cutoff for edge-weights to generate embeddings. Edge weights above this percentile cutoff will be kept. Default : 0.1

"""

import os
import sys
import datetime
import random
import pickle
import glob
import configparser
import torch
import torch.distributed as dist
import torch.multiprocessing as mp
import torch_geometric.nn as pyg_nn
from torch_geometric.data import Data
from torch.nn.parallel import DistributedDataParallel as DDP
from torch.nn import DataParallel

def main_gpu(rank, world_size):
    # Initialize distributed backend
    print("Rank intialized = {} :".format(rank))
    #dist.init_process_group(backend='nccl', init_method='env://', rank=rank, world_size=world_size)
    dist.init_process_group(backend='NCCL', rank=rank, world_size=world_size)

    # Set the device based on the rank
    device = torch.device("cuda:{}".format(rank))

    dataBaseDirectory = getBaseDirectoryOfData()

    dataVersion = sys.argv[3]
    data = getData(dataBaseDirectory,dataVersion)

    print("Moving 'data' to GPUs.....")
    data = data.to(device)
    print("Completed moving 'data' to GPUs....Moving onto training...")

    # Gather model and set to eval mode
    modelChoice = sys.argv[2]
    hiddensz = int(sys.argv[4])
    model = getModel(dataBaseDirectory,modelChoice,hiddensz)
    model.eval()
    # Perform the forward pass on each GPU
    with torch.no_grad():
        output = model(x=data.x, edge_index=data.edge_index)

    # Gather the outputs from all GPUs
    all_outputs = [torch.zeros_like(output) for _ in range(world_size)]
    dist.all_gather(all_outputs, output)
    print("Completed gathering from all GPUs....")

    # Only the first GPU (rank 0) will save the complete output to the file
    if rank == 0:
        embeddings = torch.cat(all_outputs, dim=0)
        # Save the complete output to disk
        embeddingsDirectoryPath = os.path.join(dataBaseDirectory, "saved_files", "embeddings")
        folderWithinEmbeddings = modelChoice.split('.')[0]
        fullWritePath = os.path.join(embeddingsDirectoryPath, folderWithinEmbeddings)
        # Check if the directory exists. If not, create it.
        if not os.path.exists(fullWritePath):
            os.makedirs(fullWritePath)
            print(f"Directory '{fullWritePath}' created successfully.")
        timeStamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")  # Use subsequently
        embedding_file_name = '{}/{}'.format(fullWritePath, "embedding_{}_percentile_{}.pkl".format(percentile*100,timeStamp))
        print("Saving embeddings for data to : {}".format(embedding_file_name))
        with open(embedding_file_name, 'wb') as file:
            pickle.dump(embeddings, file)


def main_cpu(rank, world_size):
    # Initialize distributed backend
    print("Rank initialized = {} :".format(rank))

    master_ip = 'localhost'  # Replace with the IP address of the master node
    port = '12345'  # Replace with the desired port number
    address = 'tcp://{}:{}'.format(master_ip, port)
    dist.init_process_group(backend='gloo', init_method=address, rank=rank, world_size=world_size)

    dataBaseDirectory = getBaseDirectoryOfData()
    dataVersion = sys.argv[3]
    data = getData(dataBaseDirectory,dataVersion)
    print("Moving 'data' to CPUs.....")
    # Move the 'data' to the current rank's CPU
    data = data.to(rank)
    print("Completed moving 'data' to CPU....")

    # Gather model and set to eval mode
    modelChoice = sys.argv[2]
    hiddensz = int(sys.argv[4])
    model = getModel(dataBaseDirectory,modelChoice,hiddensz)
    model = model.to(rank)
    model = DDP(model, device_ids=[rank])  # Wrap the model with DDP for distributed data parallel

    # Set to non-training mode and generate embeddings
    model.eval()
    embeddings = model(x=data.x, edge_index=data.edge_index)
    print("The embeddings have the following shape: \n{}".format(embeddings.shape))

    # Save to disk
    embeddingsDirectoryPath = os.path.join(dataBaseDirectory, "saved_files", "embeddings")
    folderWithinEmbeddings = modelChoice.split('.')[0]
    fullWritePath = os.path.join(embeddingsDirectoryPath, folderWithinEmbeddings)
    # Check if the directory exists. If not, create it.
    if not os.path.exists(fullWritePath):
        os.makedirs(fullWritePath)
        print(f"Directory '{fullWritePath}' created successfully.")
    timeStamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")  # Use subsequently
    embedding_file_name = '{}/{}'.format(fullWritePath, "embedding_{}_percentile_{}.pkl".format(percentile*100,timeStamp))
    print("Saving embeddings for data to : {}".format(embedding_file_name))
    with open(embedding_file_name, 'wb') as file:
        pickle.dump(embeddings, file)

def getBaseDirectoryOfData():
    config_options = configparser.ConfigParser()
    script_directory = os.path.dirname(os.path.abspath(__file__))
    conf_dir = os.path.join(script_directory, 'conf')
    config_options.read(os.path.join(conf_dir, 'models.conf'))
    dataBaseDirectory = dict(config_options.items("MODELS_CONFIGS")).get('datawarehousedir')
    return dataBaseDirectory

def getData(dataBaseDirectory,dataVersion):
    # Load 'data' object directly from saved pickle file that was created earlier
    versionDirectoryName = '{}/{}'.format(dataBaseDirectory + "/saved_files/data_representations", dataVersion)

    # Pick out the 1st from the list (assume there is only 1 in each version directory as per design)
    search_path = os.path.join(versionDirectoryName, 'data_obj_*.pkl')

    try:
        matching_file = glob.glob(search_path)[0]
    except:
        print("""
        Error: Check if folder you provided as argument exists inside 'saved_folder/data_representations'.
        Path to review the contents is : {}.
        """.format(dataBaseDirectory))
        sys.exit(1)  # Exit with a non-zero status code to indicate an error

    with open(matching_file, 'rb') as file:
        data = pickle.load(file)
    print("The entire 'data' object has the below representation : \n{}".format(data))
    return data


def getModel(dataBaseDirectory,modelChoice,hiddensz):
    modelDirectoryPath = dataBaseDirectory + "/saved_files/model_artefacts"
    file_path = '{}/{}'.format(modelDirectoryPath, modelChoice)

    model = GCN(num_features=data.x.size(1), hidden_size=hiddensz, embedding_size=10)
    model.load_state_dict(torch.load(file_path))
    return model


def trimDownEdgesByWeightCutoff(data, percentile=0.05):
    k = int(percentile * data.edge_weight.size(0))
    cutoff, _ = torch.kthvalue(data.edge_weight, k) # k is the percentile index, if data.edge_weight were to be ordered
    print("Based on percentile {} provided, cutoff was found to be {}".format(percentile,cutoff))
    # Generate mask based on cutoff found using the percentile
    mask = data.edge_weight > cutoff
    edge_weights_out = data.edge_weight[mask]
    edge_indices_out = data.edge_index[:, mask]
    return Data(x=data.x, edge_index=edge_indices_out, edge_weight=edge_weights_out, num_nodes=data.x.size(0))

# Consider to place this into a model library to import when needed
# Define the graph convolutional network model based on the 'MessagePassing' class
class GCN(pyg_nn.MessagePassing):
    def __init__(self, num_features, hidden_size, embedding_size):
        super(GCN, self).__init__(
            aggr='add')  # Message Passing aggregation is 'aggr' (can be sum/mean/min/max) from neighboring nodes
        self.conv1 = pyg_nn.GCNConv(num_features, hidden_size, cached=False)
        self.conv2 = pyg_nn.GCNConv(hidden_size, embedding_size, cached=False)
        self.conv1.reset_parameters()
        self.conv2.reset_parameters()

    def forward(self, x, edge_index):
        x = self.conv1(x=x, edge_index=edge_index)
        x = torch.relu(x)
        x = self.conv2(x=x, edge_index=edge_index)
        return x


if __name__ == "__main__":

    if len(sys.argv) < 5:
        print("""
        Total of 3 arguments are required:
        Argument 1 : Mode of training. Choice of 'distributedGPU' or 'distributedCPU' or 'non-distributed' mode.
        Argument 2 : Name of the model pickle file as seen in '/saved_files/model_artefacts'
        Argument 3 : Name of the version folder of the data to use as seen in '/saved_files/data_representations'
        Argument 4 : Hidden layer size of model.pkl chosen in argument 2
        Please retry again and make sure to pass atleast these 3 arguments.
        """)
        sys.exit(1)  # Exit with a non-zero status code to indicate an error

    mode = sys.argv[1]
    modelChoice = sys.argv[2]
    dataVersion = sys.argv[3]
    hiddensz = int(sys.argv[4])
    print("Mode chosen : '{}'".format(mode))

    dataBaseDirectory = getBaseDirectoryOfData()
    print("Base directory for data is located at : {} \n".format(dataBaseDirectory))
    print("Is torch cuda available? : {}".format(torch.cuda.is_available()))

    if mode == 'distributedGPU':
        world_size = 2 # Set the number of GPUs available for distributed inference
        # Use torch.multiprocessing.spawn to launch a separate process for each GPU
        mp.spawn(main_gpu, args=(world_size,), nprocs=world_size)
    elif mode == 'distributedCPU':
        world_size = 2
        # Use torch.multiprocessing.spawn to launch a separate process for each CPU
        mp.spawn(main_cpu, args=(world_size,), nprocs=world_size)
    elif mode == 'non-distributed':
        data = getData(dataBaseDirectory,dataVersion)
        model = getModel(dataBaseDirectory,modelChoice,hiddensz)

        # Move the model and data to the GPU,if applicable
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        model.to(device)
        data = data.to(device)

        model = DataParallel(model)  # Set the model to use DataParallel for multi-CPU computation

        # Trim down the edge weights to be able to generate embeddings for significant edge weights

        if len(sys.argv) > 5:
            try:
                percentile = float(sys.argv[5])
            except:
                print("Error: Invalid percentile value provided. Going for default....")
                percentile = 0.1 # Setting the default
        else:
            percentile = 0.1
        print("Cut-off percentile for edge weights = {}%. Beginning trimming down edges....".format(percentile*100))
        data = trimDownEdgesByWeightCutoff(data, percentile=percentile)
        print("After trimming off edge weights based on percentile, the number of pairs of edges remaining = {}".format(data.edge_weight.size(0)))
        # Set to non-training mode and generate embeddings
        model.eval()
        embeddings = model(x=data.x, edge_index=data.edge_index)
        print("The embeddings have the following shape: \n{}".format(embeddings.shape))

        # Save to disk
        embeddingsDirectoryPath = os.path.join(dataBaseDirectory, "saved_files", "embeddings")
        folderWithinEmbeddings = modelChoice.split('.')[0]
        fullWritePath = os.path.join(embeddingsDirectoryPath, folderWithinEmbeddings)
        # Check if the directory exists. If not, create it.
        if not os.path.exists(fullWritePath):
            os.makedirs(fullWritePath)
            print(f"Directory '{fullWritePath}' created successfully.")
        timeStamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")  # Use subsequently
        embedding_file_name = '{}/{}'.format(fullWritePath, "embedding_{}_percentile_{}.pkl".format(percentile*100,timeStamp))
        print("Saving embeddings for data to : {}".format(embedding_file_name))
        with open(embedding_file_name, 'wb') as file:
            pickle.dump(embeddings, file)
    else:
        print("Error: Mode provided is invalid. Choose 'distributed' or 'regular'")
        sys.exit(1)
