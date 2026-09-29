-- Exact rounding of a floor quotient and its nonnegative remainder.
local module = {}

function module.parts(whole, remainder, denominator, policy)
  assert(denominator > 0 and remainder >= 0 and remainder < denominator)
  if policy == "floor" then return whole end
  if policy == "ceil" then return whole + (remainder > 0 and 1 or 0) end
  if policy == "toward-zero" then return whole + (whole < 0 and remainder > 0 and 1 or 0) end
  assert(policy == "nearest-away-from-zero", "unsupported rounding policy")
  return whole
    + ((2 * remainder > denominator or (2 * remainder == denominator and whole >= 0)) and 1 or 0)
end

function module.ratio(numerator, denominator, policy)
  return module.parts(numerator // denominator, numerator % denominator, denominator, policy)
end

return module
