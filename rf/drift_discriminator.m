%% Oscillator-drift correction + sea-Doppler / rig-drift discriminator (MATLAB)
% AI-assisted (Claude). MATLAB companion to drift_discriminator.py. Tracks the
% beacon's instantaneous frequency, removes the slow oscillator/rig drift (poly
% fit), and tests the residual for the band's symmetric Bragg lines (+/- fB) to
% tell genuine ocean-scatter Doppler from rig drift.
%
% Run:  >> drift_discriminator

function drift_discriminator
  fs = 1000; dur = 31; n = round(fs*dur); t = (0:n-1).'/fs;
  freqMHz = 144; fB = ocean_bragg(freqMHz);

  cases = {'sea + big rig drift', true, 0.20;
           'sea, clean rig',      true, 0.01;
           'rig drift only',      false,0.20};
  fprintf('2 m: Bragg fB = %.2f Hz\n', fB);
  for k=1:size(cases,1)
    [x,~] = synth(fs,n,t,fB,cases{k,2},cases{k,3});
    f = track_freq(x,fs);
    [resid,drate] = remove_drift(f,fs,2);
    score = bragg_score(resid,fs,fB);
    verdict = "rig drift only"; if score>4, verdict = "SEA DOPPLER"; end
    fprintf('%-22s: est drift %+.3f Hz/s (true %+.2f) | Bragg %.1f -> %s\n', ...
            cases{k,1}, drate, cases{k,3}, score, verdict);
  end
end

function fB = ocean_bragg(fMHz)
  c=299792458; g=9.81; L=c/(fMHz*1e6); lo=L/2; v=sqrt(g*lo/(2*pi)); fB=2*v/L;
end
function [x,g] = synth(fs,n,t,fB,sea,drift)
  carrier = exp(1i*(2*pi*50*t + 2*pi*0.5*drift*t.^2));
  if sea
    w=randn(n,1)+1i*randn(n,1); f=((0:n-1).'-floor(n/2))/n*fs;
    psd=exp(-0.5*((f-fB)/0.3).^2)+exp(-0.5*((f+fB)/0.3).^2);
    g=ifft(fft(w).*ifftshift(sqrt(psd))); g=g/sqrt(mean(abs(g).^2));
    x=carrier.*g;
  else
    g=ones(n,1); x=carrier.*(1+0.02*randn(n,1));
  end
  p=mean(abs(x).^2); x=x+sqrt(p/100/2)*(randn(n,1)+1i*randn(n,1));
end
function f = track_freq(x,fs)
  ph=unwrap(angle(x)); f=diff(ph)/(2*pi)*fs; f=movmean(f,25);
end
function [resid,drate] = remove_drift(f,fs,order)
  t=(0:numel(f)-1).'/fs; c=polyfit(t,f,order); resid=f-polyval(c,t); drate=c(order);
end
function s = bragg_score(resid,fs,fB)
  r=resid-mean(resid); R=abs(fft(r.*hann(numel(r)))); fr=(0:numel(r)-1)/numel(r)*fs;
  m=fr>fB-0.35 & fr<fB+0.35; base=median(R(fr>0.05 & fr<fs/2))+1e-9;
  s=max(R(m))/base;
end
