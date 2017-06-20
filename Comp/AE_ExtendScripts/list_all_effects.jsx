function listAllEffects() {
    var _effects = app.effects;
    for (var i=0; i<_effects.length; i++) {
        $.writeln('"' + _effects[i].displayName + '", "' + _effects[i].category + '", "' + _effects[i].matchName + '"')
    }
}

listAllEffects()