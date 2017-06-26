function createUI(thisObj) {
	var _win = (thisObj instanceof Panel) ? thisObj : new Window("palette", "OpticalFlares");

	_win.Btn = _win.add("button", [25,110,105,130], '创建光学光斑');
	_win.Btn.onClick = function()
        {
            createOpticalFlare();
        }

    if (!(thisObj instanceof Panel)) {_win.show()};

    return _win
}

function createOpticalFlare(Comp) {
    var _layer;
    var _footage;
    var _comp;
    var _active

    if (!app.project) {app.newProject()};

    app.beginUndoGroup('创建光学光斑');
    
    _active = app.project.activeItem
    if (_active instanceof CompItem) {
        if (_active.selectedLayers && _active.selectedLayers[0] instanceof AVLayer) {
            _footage = _active.selectedLayers[0].source
        } else {
            _footage = importFootage();
        }
    } else if (_active instanceof FootageItem) {
        _footage = _active
    } else {
        _footage = importFootage()
    };

    if (!_footage) {return false;}
    
    _comp = (_active instanceof CompItem) ? _active :Comp || app.project.items.addComp(
        '光学光斑',
        _footage.width,
        _footage.height,
        _footage.pixelAspect,
        _footage.duration,
        _footage.frameRate
    );
    if (!(_comp instanceof CompItem)) {return false};

    _layer = _comp.layers.add(_footage)
    _layer.enabled = false;
    _layer.name = '_光学光斑源图层';
    _layer.comment = "脚本创建的";
    _layer = _comp.layers.addSolid([1,1,1], '光学光斑', _comp.width, _comp.height, 1.0);
    _layer.comment = "脚本创建的";
    createEffect(_layer)

    _comp.openInViewer();

    app.endUndoGroup();
    return _comp;

    function createEffect(Layer) {
        // effect(12): Souce Type
        // effect(31): Souce Layer
        var _effect;

        _effect = Layer.Effects.addProperty("VIDEOCOPILOT OpticalFlares");
        _effect(12).setValue(5);

        // Refresh effect.
        _effect.duplicate().remove();
        _effect = Layer.Effects(1);

        _effect(31).setValue(2);
    }
    
    function importFootage() {
        var _footage;

        _footage = app.project.importFileWithDialog()
        if (_footage === null) {return false};
        _footage = _footage[0]
        _footage.mainSource.conformFrameRate = 25;
        
        return _footage
    }
};

createUI(this);