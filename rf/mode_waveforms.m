% Einstein - mode_waveforms.m
% Representative MATLAB/Octave generators for the RF Modes Library
% (see rf/MODES.md and rf/modes_library.py). Educational reference
% implementations - tone/parameter-accurate, not full protocol stacks.
% Runs in MATLAB or GNU Octave. All clear-text; no encryption.
%
% Quick demo:
%   fs = 48000;
%   x = afsk1200([0 1 1 0 1 0 0 1], fs);           % Bell 202 packet tones
%   y = rtty_fsk([1 0 1 1 0], fs);                 % 45.45 baud, 170 Hz shift
%   z = mfsk_tones([3 6 4 7 2 0 5 1], fs,6.25,1000,6.25);  % FT8-style 8-FSK
%   p = psk31('CQ');                               % BPSK31 with Varicode
%   c = conv_encode([1 0 1 1 0 0 1]);              % r=1/2 K=7 (171/133)
%   d = dsss([1 0 1 1], [1 0 1 1 0 0 1], 4);       % direct-sequence spread
%   s = costas_preamble(fs);                        % sync preamble tones

% ---------------------------------------------------------------- AFSK 1200
function x = afsk1200(bits, fs)
  baud = 1200; mark = 1200; space = 2200; sps = round(fs/baud);
  phase = 0; cur = mark; x = zeros(1, sps*numel(bits)); k = 1;
  for b = bits                         % NRZI: 0 toggles tone, 1 keeps it
    if b == 0
      if cur == mark, cur = space; else, cur = mark; end
    end
    for n = 1:sps
      phase = phase + 2*pi*cur/fs;     % phase-continuous
      x(k) = sin(phase); k = k + 1;
    end
  end
end

% ---------------------------------------------------------------- RTTY / FSK
function x = rtty_fsk(bits, fs)
  baud = 45.45; shift = 170; centre = 2125;        % mark=centre+shift/2
  mark = centre + shift/2; space = centre - shift/2; sps = round(fs/baud);
  phase = 0; x = zeros(1, sps*numel(bits)); k = 1;
  for b = bits
    f = mark*(b==1) + space*(b==0);
    for n = 1:sps
      phase = phase + 2*pi*f/fs; x(k) = sin(phase); k = k + 1;
    end
  end
end

% ---------------------------------------------------- MFSK tone synthesiser
% sym: tone indices 0..M-1. FT8: baud=6.25, df=6.25, M=8. Einstein Robust:
% baud=31.25, df=31.25, M=8, f0=1375.
function x = mfsk_tones(sym, fs, baud, f0, df)
  sps = round(fs/baud); phase = 0; x = zeros(1, sps*numel(sym)); k = 1;
  for s = sym
    f = f0 + s*df;
    for n = 1:sps
      phase = phase + 2*pi*f/fs; x(k) = sin(phase); k = k + 1;
    end
  end
end

% ---------------------------------------------------------------- PSK31
% BPSK at 31.25 baud with Varicode + phase reversals on '0' bits.
function x = psk31(text, fs)
  if nargin < 2, fs = 8000; end
  baud = 31.25; sps = round(fs/baud);
  bits = [];
  for c = text
    bits = [bits varicode(c) 0 0];                 % 00 separates characters
  end
  phase = 1; x = [];                               % phase in {+1,-1}
  for b = bits
    if b == 0, phase = -phase; end                 % 0 -> reverse carrier
    seg = phase * ones(1, sps);
    x = [x seg];
  end
  t = (0:numel(x)-1)/fs;
  x = x .* sin(2*pi*1000*t);                        % 1000 Hz BPSK carrier
end

function b = varicode(ch)
  % Minimal Varicode subset for the demo (space + A..Z uppercased).
  map = containers.Map('KeyType','char','ValueType','char');
  map(' ')='1'; map('E')='11'; map('T')='101'; map('A')='1011';
  map('O')='10111'; map('C')='10101'; map('Q')='110111101';
  k = upper(ch); if ~isKey(map,k), k = 'E'; end
  b = double(map(k)) - double('0');
end

% ---------------------------------------- Convolutional encoder r=1/2 K=7
% NASA/CCSDS polynomials 171/133 (octal) - same as Einstein/WSPR-class FEC.
function out = conv_encode(bits)
  g1 = 121; g2 = 91; state = 0; out = [];           % octal 171 / 133
  for b = [bits 0 0 0 0 0 0]                        % flush 6 tail bits
    state = bitand(bitor(bitshift(state,1), b), 127);
    out(end+1) = mod(sum(bitget(bitand(state,g1),1:7)), 2);
    out(end+1) = mod(sum(bitget(bitand(state,g2),1:7)), 2);
  end
end

% ------------------------------------------------- DSSS direct-sequence
% Spread each data bit by a PN chip sequence (BPSK). Processing gain =
% numel(pn). sps = samples per chip.
function tx = dsss(bits, pn, sps)
  d = 2*bits(:).' - 1; c = 2*pn(:).' - 1;
  chips = reshape(c.' * d, 1, []);                  % outer product, chip-major
  tx = repelem(chips, sps);
end

% ------------------------------------------------- FM modulator (voice/data)
function x = fm_mod(msg, fs, fdev)
  if nargin < 3, fdev = 3000; end                   % 3 kHz deviation
  msg = msg(:).' / max(1e-9, max(abs(msg)));
  phase = 2*pi*fdev*cumsum(msg)/fs;
  x = cos(phase);
end

% ------------------------------------------------- Costas-array preamble
% 16-symbol Costas sequence used by Einstein Robust / FT8-family sync.
function x = costas_preamble(fs)
  seq = [3 6 4 7 2 0 5 1 1 5 0 2 7 4 6 3];
  x = mfsk_tones(seq, fs, 31.25, 1375, 31.25);
end
