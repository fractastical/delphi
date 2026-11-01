model TightBand {
  species A @init 0.0
  species B @init 0.0
  reaction influx :  -> A   @mass_action(vin)
  reaction step   : A -> B  @mass_action(k1)
  reaction efflux : B ->    @mass_action(k2)
  param vin in [10.0, 20.0] @experiment(replicates=4, p=0.01)
  param k1  in [1.0, 5.0]   @assumed
  param k2  in [1.0, 5.0]   @assumed
  steady_state
  property too_tight : flux(efflux) in [12.0, 18.0]
}
