%% Evaporation / surface-duct refractivity model  (MATLAB)  — AI-assisted (Claude)
% Predicts over-water VHF/UHF ducting from bulk marine weather, for Einstein's
% ocean-scatter / sea-path propagation studies. Computes the modified refractivity
% profile M(z) and the evaporation duct height (EDH), and flags surface-based
% inversions. Simplified (neutral log profiles); for research/triage, not a
% replacement for a full NPS/PJ bulk model.
%
% Inputs (edit below): SST, air temp, RH at reference height, pressure, wind.
% Run:  >> evap_duct

function evap_duct
  % ---- bulk marine inputs ----
  SST  = 29;      % sea surface temp (C)
  Ta   = 27;      % air temp at zr (C)
  RH   = 70;      % relative humidity at zr (%)
  P    = 1015;    % surface pressure (hPa)
  U    = 6;       % wind speed at zr (m/s)
  zr   = 10;      % reference measurement height (m)

  z  = logspace(log10(0.1), log10(60), 200).';   % heights (m)
  z0 = 1.5e-4;                                    % sea roughness length (m)

  % surface (saturated over seawater, salinity -2%) and reference humidity
  eS = 0.98*esat(SST);  qS = spechum(eS,P);
  eR = (RH/100)*esat(Ta); qR = spechum(eR,P);

  % neutral log profiles of T and q between surface and zr
  f  = log(z/z0)/log(zr/z0); f = min(max(f,0),1.2);
  Tz = SST + (Ta-SST).*f;
  qz = qS  + (qR-qS ).*f;
  ez = qz.*P./(622+0.378*qz);        % vapor pressure from specific humidity
  Nz = 77.6*P./(Tz+273.15) + 3.73e5*ez./(Tz+273.15).^2;
  Mz = Nz + 0.157*z;                 % modified refractivity

  % evaporation duct height = height of the M minimum (dM/dz = 0)
  [~,iMin] = min(Mz); EDH = z(iMin);
  astd = Ta - SST;
  trapped = any(diff(Mz)<0);

  fprintf('SST %.1f  Ta %.1f  RH %.0f%%  U %.1f m/s\n', SST,Ta,RH,U);
  fprintf('Air-sea dT = %+.1f C | humidity deficit %.1f g/kg\n', astd, qS-qR);
  fprintf('Evaporation duct height EDH = %.1f m | trapping layer present: %d\n', EDH, trapped);
  if astd>1.5, fprintf('Warm air over cooler sea -> surface-based (inversion) duct likely.\n'); end
  if EDH>15, fprintf('Strong evaporation duct -> VHF/UHF over-water enhancement likely.\n');
  elseif EDH>6, fprintf('Moderate evaporation duct.\n'); else, fprintf('Weak/no evaporation duct.\n'); end

  figure; plot(Mz,z,'LineWidth',1.6); grid on; set(gca,'YDir','normal');
  xlabel('Modified refractivity M'); ylabel('Height (m)');
  title(sprintf('M(z): EDH \\approx %.1f m  (dT %+.1f C)', EDH, astd));
  hold on; yline(EDH,'--r');
end

function e = esat(T),  e = 6.112*exp(17.62*T./(243.12+T)); end          % hPa
function q = spechum(e,P), q = 0.622*e./(P-0.378*e)*1000; end            % g/kg
