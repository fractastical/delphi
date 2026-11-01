# Over the reals: v_step = vin/2 = 5.5, so efflux = 5.5 and the band [0,0] is FALSE.
# Over the integers 2*v_step = 11 has no solution, so the hypotheses are contradictory.
model IntGap {
  species A @init 0.0
  species B @init 0.0
  reaction influx :  -> A      @mass_action(vin)
  reaction step   : 2 A -> B   @mass_action(k1)
  reaction efflux : B ->       @mass_action(k2)
  param vin in [11.0, 11.0] @assumed
  param k1  in [1.0, 5.0]   @assumed
  param k2  in [1.0, 5.0]   @assumed
  steady_state
  property absurd : flux(efflux) in [0.0, 0.0]
}
