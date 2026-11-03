%% Neural receiver (training scaffold) — HOMER/AVIAN weak-signal decoder  (MATLAB)
% AI-assisted (Claude). Tier-1 research scaffold for the architecture in
% RECEIVER_ARCHITECTURE.md: train a small 1-D CNN that maps the per-symbol tone
% energies (16 soft features/symbol) to soft bits, learning to beat the hand-written
% max-log detector under Watterson/ocean-scatter fading. Trains on GPU if present.
%
% Requires: Deep Learning Toolbox (+ Parallel Computing Toolbox for GPU/sweeps).
% This is a STARTING POINT you run and tune in MATLAB — generate more/real data,
% deepen the net, then exportONNXNetwork for the Python-deployed decoder.
%
% Run:  >> neural_receiver

function neural_receiver
  rng(0);
  M = 16; bps = log2(M);         % 16-FSK, 4 bits/symbol (matches pigeon_rf2)
  nSymPerFrame = 110;            % ~ coded symbols per HOMER frame
  nTrain = 4000; nVal = 800;

  % ---- synthesize training features: 16 tone energies per symbol + the true bits ----
  [Xtr,Ytr] = makeSet(nTrain, nSymPerFrame, M, bps);
  [Xva,Yva] = makeSet(nVal,  nSymPerFrame, M, bps);

  % feature tensor for a 1-D CNN: [features=M, 1, channels=1, samples]
  Xtr = reshape(Xtr, M, 1, 1, []);  Xva = reshape(Xva, M, 1, 1, []);
  Ytr = categorical(Ytr(:));        Yva = categorical(Yva(:));

  layers = [
    imageInputLayer([M 1 1],'Normalization','zerocenter','Name','in')
    convolution2dLayer([5 1],32,'Padding','same'); batchNormalizationLayer; reluLayer
    convolution2dLayer([5 1],32,'Padding','same'); batchNormalizationLayer; reluLayer
    fullyConnectedLayer(64); reluLayer; dropoutLayer(0.2)
    fullyConnectedLayer(bps)                       % 4 bit-logits/symbol
    % note: multi-label per symbol -> train bit-wise; here shown as 1 bit for clarity.
    sigmoidLayer                                    % soft bits in [0,1]
    ];
  % For the full 4-bit-per-symbol target, wrap this as 4 binary heads or train per
  % bit-plane; kept compact here. See RECEIVER_ARCHITECTURE.md.

  opts = trainingOptions('adam', ...
     'MaxEpochs',20, 'MiniBatchSize',256, 'InitialLearnRate',1e-3, ...
     'ValidationData',{Xva,Yva}, 'Shuffle','every-epoch', ...
     'ExecutionEnvironment','auto', ...     % uses GPU automatically if available
     'Plots','training-progress', 'Verbose',true);

  fprintf('GPU available: %d\n', (gpuDeviceCount>0));
  net = trainNetwork(Xtr, Ytr, layers, opts);   %#ok<NASGU>

  % ---- compare neural vs classical max-log on a held-out fading set ----
  % (classical: bit = argmax tone-energy parity, i.e. the current _soft_bits rule)
  fprintf('Trained. Next: evaluate BER vs soft-Viterbi, then exportONNXNetwork(net,"avian_nn.onnx").\n');
  % exportONNXNetwork(net, 'avian_nn.onnx');     % -> deploy in Python (onnxruntime)
end

function [X,Y] = makeSet(nFrames, nSym, M, bps)
% Build per-symbol tone-energy features under random SNR + fading, with true bits.
  X = zeros(M, nFrames*nSym); Y = zeros(1, nFrames*nSym); col = 1;
  for f = 1:nFrames
    snr = -22 + 8*rand;                      % dB-ish spread across the threshold
    fd  = 0.5 + 1.5*rand;                    % Doppler (Hz) — fading/ocean-scatter proxy
    for s = 1:nSym
      sym = randi([0 M-1]);
      P = zeros(M,1); P(sym+1) = 1;          % ideal tone
      % fading amplitude + AWGN on the energies (proxy for the true demod front-end)
      g = abs(1 + (fd/3)*(randn+1i*randn)/sqrt(2));
      P = g*P + 10^(-snr/20)*abs(randn(M,1));
      X(:,col) = P/ (mean(P)+1e-9);
      Y(col)   = bitget(sym, 1);             % 1 bit shown; extend to all bps bits
      col = col+1;
    end
  end
end
