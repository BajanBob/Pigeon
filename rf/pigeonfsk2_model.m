%% PigeonFSK-2 waveform model & sensitivity sweep  (MATLAB)
% AI-assisted weak-signal amateur position waveform. This script models the
% mode in MATLAB so you can (a) reproduce the ~-21 dB/2500 Hz threshold the
% Python reference achieves, and (b) push LOWER by swapping the r=1/2 K=7
% convolutional FEC for LDPC, and by validating on an HF (Watterson) fading
% channel instead of plain AWGN.
%
% Requires: Communications Toolbox.  (LDPC section also uses it.)
% Run:  >> pigeonfsk2_model
%
% NOTE: amateur radio forbids encryption. This waveform is CLEAR TEXT. The
% model sends random payload bits only to measure error-rate performance.

clear; clc = @()fprintf('\n');

%% ---- waveform parameters (match pigeon_rf2.py) ----
Fs      = 12000;        % sample rate
symLen  = 3072;         % samples/symbol -> baud = 3.906
M       = 16;           % 16-FSK
baud    = Fs/symLen;
freqsep = Fs/symLen;    % orthogonal tone spacing (exact FFT bins)
nsamp   = symLen;
infoBits= 200;          % fixed frame: 23B payload + 2B CRC = 200 bits

%% ---- choose FEC: 'conv' (shipping) or 'ldpc' (go lower) ----
fecType = 'conv';       % <-- change to 'ldpc' to test the stronger code

switch fecType
  case 'conv'
    trellis = poly2trellis(7,[171 133]);      % r=1/2 K=7, same as Python
    enc = @(b) convenc([b; zeros(6,1)], trellis);
    % unquantized soft-decision Viterbi:
    vd  = comm.ViterbiDecoder(trellis,'InputFormat','Unquantized', ...
                              'TerminationMethod','Terminated');
    dec = @(llr) vd(llr);
    rate = 1/2;
  case 'ldpc'
    % DVB-S2 rate-1/2 LDPC (64800) is overkill for 200 bits; use a short code.
    % Here we show the wiring; tune H for your frame size.
    H = dvbs2ldpc(1/2);
    ldpcEnc = comm.LDPCEncoder(H);
    ldpcDec = comm.LDPCDecoder(H,'DecisionMethod','Hard','MaximumIterationCount',50);
    enc = @(b) ldpcEnc(b);     % expects 32400 info bits for this H — pad/segment as needed
    dec = @(llr) ldpcDec(llr);
    rate = 1/2;
end

%% ---- SNR sweep (reference bandwidth = 2500 Hz, FT8 convention) ----
snr2500 = -14:-1:-23;           % dB in 2500 Hz
nFrames = 200;
Rb = infoBits * baud / ( (infoBits/ (log2(M)) ) );  % info bit rate approx
% info bit rate: coded symbols = ceil(infoBits/rate / log2(M)); time = that*symLen/Fs
codedBits   = infoBits/rate + 6;              % +flush for conv
nSymData    = ceil(codedBits/log2(M));
frameTime   = (nSymData+16)*symLen/Fs;        % +16 sync symbols
Rb          = infoBits/frameTime;             % bits/s actually delivered

pDecode = zeros(size(snr2500));

for ii = 1:numel(snr2500)
  ok = 0;
  % convert SNR-in-2500Hz to EbN0 for the AWGN function:
  %   SNR2500 = EbN0 + 10log10(Rb/2500)
  EbN0 = snr2500(ii) - 10*log10(Rb/2500);
  for f = 1:nFrames
    bits = randi([0 1], infoBits, 1);
    switch fecType
      case 'conv', coded = enc(bits);
      otherwise,   coded = enc(bits);   % ensure sizes match your H
    end
    % pad coded to a multiple of log2(M) and map to 16-FSK symbols
    pad = mod(-numel(coded), log2(M));
    codedp = [coded; zeros(pad,1)];
    syms = bi2de(reshape(codedp,log2(M),[]).','left-msb');
    tx   = fskmod(syms, M, freqsep, nsamp, Fs, 'discont', 'gray');

    % ---- channel: AWGN (swap for Watterson HF fading, see below) ----
    rx = awgn(tx, EbN0 + 10*log10(log2(M)) - 10*log10(nsamp), 'measured');
    % (For HF fading instead:)
    %  chan = stdchan('iturHFMM', Fs, 1);     % ITU-R moderate HF multipath+Doppler
    %  rx   = awgn(chan(tx), ...);

    % ---- noncoherent soft demod -> soft bits -> FEC decode ----
    sd = fskdemod(rx, M, freqsep, nsamp, Fs);           % hard demod (demo)
    rbits = de2bi(sd,log2(M),'left-msb').'; rbits = rbits(:);
    rbits = rbits(1:numel(coded));
    % (For true soft-decision, compute per-tone energies and form LLRs, as the
    %  Python _soft_bits() does, then feed vd() with Unquantized inputs.)
    llr = 1 - 2*double(rbits);                           % placeholder hard->soft
    switch fecType
      case 'conv', dech = dec(llr); dech = dech(1:infoBits);
      otherwise,   dech = dec(llr);
    end
    ok = ok + isequal(dech(1:infoBits), bits);
  end
  pDecode(ii) = ok/nFrames;
  fprintf('SNR %4d dB/2500Hz : decode %.0f%%\n', snr2500(ii), 100*pDecode(ii));
end

figure; plot(snr2500, 100*pDecode, '-o','LineWidth',1.5); grid on;
xlabel('SNR in 2500 Hz (dB)'); ylabel('Frame decode rate (%)');
title(sprintf('PigeonFSK-2 sensitivity (%s FEC) — target < -18 dB', upper(fecType)));
yline(50,'--'); xline(-18,'--');

%% ---- To push BELOW the convolutional threshold ----
% 1) Set fecType='ldpc' above and size H to the frame (short LDPC ~ +2 dB vs conv).
% 2) Replace the placeholder LLRs with true noncoherent soft metrics:
%       per symbol, P = |FFT at the 16 tone bins|.^2;
%       for bit j:  llr_j = max(P(bit_j==0)) - max(P(bit_j==1));
%    (this is what gives the real soft-decision gain — see pigeon_rf2._soft_bits)
% 3) Validate on HF: swap AWGN for stdchan('iturHFMM',Fs,1) (Watterson) to see
%    the threshold under realistic ionospheric fading and Doppler.
% 4) Deep Learning Toolbox: train a small CNN "neural receiver" on (rx -> bits)
%    to beat the hand-written demod under fading — the genuine AI-hybrid step.
