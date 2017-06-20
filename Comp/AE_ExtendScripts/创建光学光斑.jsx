function createUI(thisObj) {
    var _bt;
    var myPanel = (thisObj instanceof Panel) ? thisObj : new Window("palette", "My Tools", [100, 100, 300, 300]);
    _bt = myPanel.add("button", [10, 10, 100, 30], "创建光学光斑");
    _bt.addEventListener("mousedown", importFootage)
    return myPanel;
}

function createOpticalFlare (Comp) {
    var _item;
    var _layer;
    var _prop;
    var _effect;
    
    app.beginUndoGroup('创建光学光斑');
    
    if (Comp) {
        _item = Comp
    } else {
        _item = app.project.activeItem;
    }
    if (! _item instanceof CompItem) {
       return;
    }
    _layer = _item.layers.addSolid([1,1,1], '光学光斑', _item.width, _item.height, 1.0);
    _layer.comment = "脚本创建的";
    _effect = _layer.Effects.addProperty("VIDEOCOPILOT OpticalFlares");
    _effect(12).setValue(5);
    // Refresh effect.
    _effect.duplicate().remove();
    _effect = _layer.Effects(1);
    // effect(31) is "Souce Layer".
    _effect(31).setValue(2);

    app.endUndoGroup();
    return _effect;
}

function importFootage() {
    var _footage;
    var _importopt;
    var _comp;

    if (!app.project) {
        app.newProject();
    }
    
    _footage = app.project.importFileWithDialog();
    if (_footage) {
        _footage = _footage[0];
    } else {
        return;
    };
    $.writeln(_footage.frameRate);
    _footage.mainSource.conformFrameRate = 25;
    
    _comp = app.project.items.addComp('光学光斑', _footage.width, _footage.height, _footage.pixelAspect, _footage.duration, _footage.frameRate);
    _comp.layers.add(_footage).enabled = false;
    createOpticalFlare(_comp);
}

importFootage();