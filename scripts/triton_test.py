#!/usr/bin/env python

# this is an adapted copy of https://github.com/tklijnsma/triton-edgenetwithcats/blob/master/client_script/client.py

# Copyright (c) 2020, NVIDIA CORPORATION. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#  * Neither the name of NVIDIA CORPORATION nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS ``AS IS'' AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY
# OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import argparse
import numpy as np
import sys
import random
import glob

# ############# HACK #############
# tritongrpcclient python api is currently limiting
# the default sending size to be ~4Mb (other api's
# seem to not suffer from this problem). This hack
# manually sets the grpc options to allow more data
# to be sent. This should be solved in future versions
# of the python api.
# See: https://github.com/NVIDIA/triton-inference-server/issues/1776#issuecomment-655894276
with open('/usr/local/lib/python3.6/dist-packages/tritongrpcclient/__init__.py', 'r') as f:
    init_file = f.read()
fixed_init_file = init_file.replace(
    'self._channel = grpc.insecure_channel(url, options=None)',
    'self._channel = grpc.insecure_channel(url, options=[(\'grpc.max_send_message_length\', 512 * 1024 * 1024), (\'grpc.max_receive_message_length\', 512 * 1024 * 1024)])'
    )
if fixed_init_file != init_file:
    print('WARNING: Hacking tritongrpcclient to allow larger requests to be sent')
    with open('/usr/local/lib/python3.6/dist-packages/tritongrpcclient/__init__.py', 'w') as f:
        f.write(fixed_init_file)
# ############# HACK #############

import tritongrpcclient

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-v',
                        '--verbose',
                        action="store_true",
                        required=False,
                        default=False,
                        help='Enable verbose output')
    parser.add_argument('-i',
                        '--int',
                        action="store_true",
                        required=False,
                        default=False,
                        help='Use int row splits instead of float')
    parser.add_argument('-m',
                        '--model_name',
                        type=str,
                        required=True,
                        help='Model name')
    parser.add_argument('-u',
                        '--url',
                        type=str,
                        required=False,
                        default='localhost:8001',
                        help='Inference server URL. Default is localhost:8001.')

    FLAGS = parser.parse_args()
    try:
        triton_client = tritongrpcclient.InferenceServerClient(url=FLAGS.url,
                                                               verbose=FLAGS.verbose)
    except Exception as e:
        print("channel creation failed: " + str(e))
        sys.exit()

    print(dir(triton_client))
    print(triton_client.get_model_repository_index())
    print(triton_client.get_server_metadata())

    print('Trying get_model_config now...')

    model_name = FLAGS.model_name 
    
    np_rs_type = 'float32'
    tr_rs_type = 'FP32'
    if FLAGS.int:    
        np_rs_type = 'int64'
        tr_rs_type = 'INT64'
        

    mconf = triton_client.get_model_config(model_name, as_json=True)
    print('config:\n', mconf)
    
    nbatches = 10
    # Loop over testdata and send inferences
    for i in range(nbatches): #just one batch per call for now
        
        inputs = []
        outputs = []
        
        nhits = 5000
        hit_data = np.random.rand(nhits,9)
        row_splits = np.array([[0],[nhits]],dtype=np_rs_type)#this should be int but lets try for now

        inputs.append(tritongrpcclient.InferInput('input_1', hit_data.shape[1], 'FP32'))
        inputs.append(tritongrpcclient.InferInput('input_2', row_splits.shape[1], tr_rs_type)) #INT64

        inputs[0].set_data_from_numpy(hit_data)
        inputs[1].set_data_from_numpy(row_splits)

        outputs.append(tritongrpcclient.InferRequestedOutput('predicted_final'))
        # predicted_final_1 doesn't matter

        results = triton_client.infer(
            model_name=model_name,
            inputs=inputs,
            outputs=outputs
            )
        output0_data = results.as_numpy('predicted_final')
        print(output0_data)
        del output0_data

    statistics = triton_client.get_inference_statistics(model_name=model_name)
    print(statistics)
    if len(statistics.model_stats) != 1:
        print("FAILED: Inference Statistics")
        sys.exit(1)
    print('PASS: infer')