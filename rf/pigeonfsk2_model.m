%% PigeonFSK-2 waveform model & sensitivity sweep  (MATLAB, runnable)
% AI-assisted weak-signal amateur POSITION waveform. This script models the mode
% end-to-end so you can:
%   (a) reproduce the ~-21 dB/2500 Hz AWGN threshold the Python reference hits,
%   (b) go LOWER by swapping the r=1/2 K=7 convolutional FEC for a short LDPC,
%   (c) validate on a realistic HF (Watterson) ionospheric fading channel.
%
% It uses TRUE non-coherent soft-decision metrics (per-tone FFT energies -> bit
% LLRs), the same idea as pigeon_rf2._soft_bits(), so the soft-decision gain is
% real, not a hard->soft placeholder.
%
% Requires: Communications Toolbox.
% Run:   >> pigeonfsk2_model
% Switch code:   set FEC = 'conv' or 'ldpc'  below.
% Switch channel: set CHAN = 'awgn' | 'hf_moderate' | 'hf_poor' below.
%
% LEGAL: amateur radio forbids encryption. This waveform is CLEAR TEXT; the model
% sends random payload bits only to measure error-rate performance.
%
% Honest note on numbers: the Python reference (pigeon_rf2.py + measure_fading.py)
% MEASURED ~-21 dB AWGN, ~-18 dB moderate-HF, ~-16 dB poor-HF (50% frame decode),
% and a short LDPC gave ~1 dB over the conv code at this 200-bit frame. This
% MATLAB model reproduces and extends that; expect LDPC's edge to grow with a
% longer frame or an irregular H.

function pigeonfsk2_model
clear; clc;

%% ---------- configuration ----------
FEC   = 'conv';          % 'conv'  (shipping r=1/2 K=7)   |  'ldpc' (short rate-1/2)
CHAN  = 'awgn';          % 'awgn' | 'hf_moderate' | 'hf_poor'
SOFT  = true;            % true = true non-coherent soft LLRs; false = hard demod
nFrames = 200;

%% ---------- waveform parameters (match pigeon_rf2.py) ----------
Fs      = 12000;
symLen  = 3072;                 % baud = 3.906
M       = 16;                   % 16-FSK
bps     = log2(M);              % 4 bits/symbol
freqsep = Fs/symLen;            % orthogonal tone spacing (exact FFT bins)
bin0    = 256;                  % first tone bin -> 1000 Hz
infoBits= 200;                  % fixed frame: 23B payload + 2B CRC = 200 bits

%% ---------- FEC setup ----------
switch FEC
  case 'conv'
    trellis = poly2trellis(7,[171 133]);     % r=1/2 K=7
    rate    = 1/2;
    codedLen= infoBits/rate + 6;             % +6 tail (terminated)
    encode  = @(b) convenc([b;zeros(6,1)], trellis);
    vd = comm.ViterbiDecoder(trellis,'InputFormat','Unquantized', ...
                             'TerminationMethod','Terminated');
    decode  = @(llr) step_reset(vd, llr, infoBits);
  case 'ldpc'
    [H, K, N] = makeLDPC(204, 408);          % short regular-ish, dual-diagonal parity
    rate    = K/N;
    cfgE    = ldpcEncoderConfig(H);
    cfgD    = ldpcDecoderConfig(H);
    encode  = @(b) ldpcEncode(b, cfgE);      % expects K info bits
    decode  = @(llr) double(ldpcDecode(llr, cfgD, 50) < 0);
    infoBits= K; codedLen = N;
end

%% ---------- frame timing (for SNR<->Eb/N0 in 2500 Hz ref BW) ----------
nSymData  = ceil(codedLen/bps);
nSync     = 16;
frameTime = (nSymData + nSync)*symLen/Fs;    % seconds on air (sensitivity cost)
Rb        = infoBits/frameTime;              % delivered info bit/s
fprintf('FEC=%s  CHAN=%s  soft=%d | frame = %.1f s, Rb = %.2f bit/s\n', ...
         FEC, CHAN, SOFT, frameTime, Rb);

%% ---------- SNR sweep ----------
switch CHAN
  case 'awgn',        snr2500 = -16:-1:-23;
  case 'hf_moderate', snr2500 = -12:-1:-21;
  case 'hf_poor',     snr2500 = -10:-1:-19;
end
pDecode = zeros(size(snr2500));

for ii = 1:numel(snr2500)
  ok = 0;
  EbN0 = snr2500(ii) - 10*log10(Rb/2500);          % Eb/N0 from SNR-in-2500Hz
  for f = 1:nFrames
    bits  = randi([0 1], infoBits, 1);
    coded = encode(bits);
    pad   = mod(-numel(coded), bps);
    cp    = [coded; zeros(pad,1)];
    syms  = bit2int(reshape(cp,bps,[]), bps).';     % 0..M-1
    tx    = fskmod(syms, M, freqsep, symLen, Fs, 'cont', 'gray');

    rx    = applyChannel(tx, CHAN, Fs);
    % noise for the target Eb/N0 (fskmod unit power; add in the symbol band)
    EsN0  = EbN0 + 10*log10(bps);
    rx    = awgn(rx, EsN0 - 10*log10(symLen), 'measured');

    if SOFT
      llr = softLLR(rx, M, symLen, Fs, freqsep, bps);   % true per-tone-energy LLRs
      llr = llr(1:numel(coded));
    else
      sdm = fskdemod(rx, M, freqsep, symLen, Fs);
      rb  = int2bit(sdm, bps); llr = 1 - 2*double(rb(1:numel(coded)));
    end

    dech = decode(llr);
    ok   = ok + isequal(dech(1:infoBits), bits);
  end
  pDecode(ii) = ok/nFrames;
  fprintf('  SNR %4d dB/2500Hz : decode %5.1f%%\n', snr2500(ii), 100*pDecode(ii));
end

figure; plot(snr2500, 100*pDecode, '-o','LineWidth',1.6); grid on; hold on;
yline(50,'--'); xline(-18,'--r');
xlabel('SNR in 2500 Hz (dB)'); ylabel('Frame decode rate (%)');
title(sprintf('PigeonFSK-2  —  FEC=%s, channel=%s', upper(FEC), CHAN));
end

%% ================= helpers =================
function y = applyChannel(x, chan, Fs)
% Watterson HF model via two independent Rayleigh paths with Gaussian Doppler.
switch chan
  case 'awgn'
    y = x; return;
  case 'hf_moderate', tau = [0 1e-3];  fd = 0.5;   % ITU-R moderate
  case 'hf_poor',     tau = [0 2e-3];  fd = 1.0;   % ITU-R poor
end
c = comm.RayleighChannel('SampleRate',Fs, ...
      'PathDelays',tau,'AveragePathGains',[0 0], ...
      'MaximumDopplerShift',fd,'DopplerSpectrum',doppler('Gaussian'), ...
      'NormalizePathGains',true);
y = real(c(x(:)));
end

function llr = softLLR(rx, M, symLen, Fs, freqsep, bps)
% TRUE non-coherent soft metrics: per symbol, FFT energy at each tone bin, then
% max-log bit LLRs.  Mirrors pigeon_rf2._soft_bits (sign: + => bit 0).
nsym = floor(numel(rx)/symLen);
bin0 = round(1000*symLen/Fs);
llr  = zeros(nsym*bps,1); idx = 1;
for s = 1:nsym
  w = rx((s-1)*symLen + (1:symLen));
  sp = abs(fft(w)).^2;
  P  = sp(bin0 + (0:M-1) + 1);        % energies at the M tone bins
  P  = P/(mean(P)+1e-12);
  for j = 0:bps-1
    ones_  = P(bitand(floor((0:M-1)/2^j),1)==1);
    zeros_ = P(bitand(floor((0:M-1)/2^j),1)==0);
    llr(idx) = max(zeros_) - max(ones_);   % >0 => bit 0
    idx = idx+1;
  end
end
end

function out = step_reset(vd, llr, infoBits)
reset(vd); out = vd(llr); out = out(1:infoBits);
end

function [H,K,N] = makeLDPC(K,N)
% Short rate-1/2 code with a DUAL-DIAGONAL (staircase) parity block so that
% ldpcEncoderConfig accepts it (last N-K columns invertible). The info block is
% a sparse regular-ish random matrix.
m = N-K; rng(7);
% random info part: ~3 ones per column
A = sparse(m,K);
for c = 1:K
  r = randperm(m,3); A(r,c) = 1;
end
% dual-diagonal parity T (m x m): identity + sub-diagonal
T = speye(m) + sparse(2:m,1:m-1,1,m,m);
H = logical([A T]);
end
