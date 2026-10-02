local runner = dofile(app.params.filter_run)
runner.execute(dofile(app.params.brightness_contrast), "Brightness/Contrast")
