local runner = dofile(app.params.filter_run)
runner.execute(dofile(app.params.despeckle), "Despeckle")
