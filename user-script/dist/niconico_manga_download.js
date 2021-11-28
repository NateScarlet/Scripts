// ==UserScript==
// @namespace https://github.com/NateScarlet/Scripts/tree/master/user-script
// @name     NicoNico manga download
// @description save loaded manga as html.
// @grant    none
// @include	 https://seiga.nicovideo.jp/watch/*
// @run-at   document-idle
// @version   2021.11.29+5b34b1f7
// ==/UserScript==

(() => {
  var __async = (__this, __arguments, generator) => {
    return new Promise((resolve, reject) => {
      var fulfilled = (value) => {
        try {
          step(generator.next(value));
        } catch (e) {
          reject(e);
        }
      };
      var rejected = (value) => {
        try {
          step(generator.throw(value));
        } catch (e) {
          reject(e);
        }
      };
      var step = (x) => x.done ? resolve(x.value) : Promise.resolve(x.value).then(fulfilled, rejected);
      step((generator = generator.apply(__this, __arguments)).next());
    });
  };

  // utils/urlLastPart.ts
  function urlLastPart(url) {
    return url.split("/").filter((i) => i).slice(-1)[0];
  }

  // utils/downloadFile.ts
  function downloadFile(file, filename = `${urlLastPart(location.pathname)} ${document.title}.md`) {
    const anchor = document.createElement("a");
    anchor.href = URL.createObjectURL(file);
    anchor.download = filename;
    anchor.style["display"] = "none";
    document.body.append(anchor);
    anchor.click();
    setTimeout(() => {
      document.body.removeChild(anchor);
      URL.revokeObjectURL(anchor.href);
    }, 0);
  }

  // utils/sleep.ts
  function sleep(duration) {
    return __async(this, null, function* () {
      return new Promise((resolve) => {
        setTimeout(resolve, duration);
      });
    });
  }

  // assets/manga_reader.html
  var manga_reader_default = '<!DOCTYPE html>\n<html>\n  <head>\n    <meta charset="UTF-8" />\n    <meta http-equiv="X-UA-Compatible" content="IE=edge" />\n    <meta name="viewport" content="width=device-width, initial-scale=1.0" />\n    <title><%- title %></title>\n    <%= `\n    <style>\n      ${style}\n    </style>\n    ` %>\n  </head>\n  <body>\n    <div class="container m-auto">\n      <h1 class="text-lg font-bold text-center"><%- title %></h1>\n      <a\n        class="block text-center text-blue-400 underline"\n        href="<%- window.location.href %>"\n        ><%- window.location.href %></a\n      >\n      <div class="sm:space-y-2 md:space-y-4">\n        <% for (const image of images) { %>\n        <img\n          class="block m-auto border"\n          src="<%- image.src %>"\n          alt="<%- image.alt %>"\n          title="<%- image.title %>"\n        />\n        <% } %>\n      </div>\n    </div>\n  </body>\n</html>\n';

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_freeGlobal.js
  var freeGlobal = typeof global == "object" && global && global.Object === Object && global;
  var freeGlobal_default = freeGlobal;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_root.js
  var freeSelf = typeof self == "object" && self && self.Object === Object && self;
  var root = freeGlobal_default || freeSelf || Function("return this")();
  var root_default = root;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_Symbol.js
  var Symbol = root_default.Symbol;
  var Symbol_default = Symbol;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_getRawTag.js
  var objectProto = Object.prototype;
  var hasOwnProperty = objectProto.hasOwnProperty;
  var nativeObjectToString = objectProto.toString;
  var symToStringTag = Symbol_default ? Symbol_default.toStringTag : void 0;
  function getRawTag(value) {
    var isOwn = hasOwnProperty.call(value, symToStringTag), tag = value[symToStringTag];
    try {
      value[symToStringTag] = void 0;
      var unmasked = true;
    } catch (e) {
    }
    var result = nativeObjectToString.call(value);
    if (unmasked) {
      if (isOwn) {
        value[symToStringTag] = tag;
      } else {
        delete value[symToStringTag];
      }
    }
    return result;
  }
  var getRawTag_default = getRawTag;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_objectToString.js
  var objectProto2 = Object.prototype;
  var nativeObjectToString2 = objectProto2.toString;
  function objectToString(value) {
    return nativeObjectToString2.call(value);
  }
  var objectToString_default = objectToString;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_baseGetTag.js
  var nullTag = "[object Null]";
  var undefinedTag = "[object Undefined]";
  var symToStringTag2 = Symbol_default ? Symbol_default.toStringTag : void 0;
  function baseGetTag(value) {
    if (value == null) {
      return value === void 0 ? undefinedTag : nullTag;
    }
    return symToStringTag2 && symToStringTag2 in Object(value) ? getRawTag_default(value) : objectToString_default(value);
  }
  var baseGetTag_default = baseGetTag;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/isObjectLike.js
  function isObjectLike(value) {
    return value != null && typeof value == "object";
  }
  var isObjectLike_default = isObjectLike;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/isSymbol.js
  var symbolTag = "[object Symbol]";
  function isSymbol(value) {
    return typeof value == "symbol" || isObjectLike_default(value) && baseGetTag_default(value) == symbolTag;
  }
  var isSymbol_default = isSymbol;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_arrayMap.js
  function arrayMap(array, iteratee) {
    var index = -1, length = array == null ? 0 : array.length, result = Array(length);
    while (++index < length) {
      result[index] = iteratee(array[index], index, array);
    }
    return result;
  }
  var arrayMap_default = arrayMap;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/isArray.js
  var isArray = Array.isArray;
  var isArray_default = isArray;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_baseToString.js
  var INFINITY = 1 / 0;
  var symbolProto = Symbol_default ? Symbol_default.prototype : void 0;
  var symbolToString = symbolProto ? symbolProto.toString : void 0;
  function baseToString(value) {
    if (typeof value == "string") {
      return value;
    }
    if (isArray_default(value)) {
      return arrayMap_default(value, baseToString) + "";
    }
    if (isSymbol_default(value)) {
      return symbolToString ? symbolToString.call(value) : "";
    }
    var result = value + "";
    return result == "0" && 1 / value == -INFINITY ? "-0" : result;
  }
  var baseToString_default = baseToString;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/isObject.js
  function isObject(value) {
    var type = typeof value;
    return value != null && (type == "object" || type == "function");
  }
  var isObject_default = isObject;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/identity.js
  function identity(value) {
    return value;
  }
  var identity_default = identity;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/isFunction.js
  var asyncTag = "[object AsyncFunction]";
  var funcTag = "[object Function]";
  var genTag = "[object GeneratorFunction]";
  var proxyTag = "[object Proxy]";
  function isFunction(value) {
    if (!isObject_default(value)) {
      return false;
    }
    var tag = baseGetTag_default(value);
    return tag == funcTag || tag == genTag || tag == asyncTag || tag == proxyTag;
  }
  var isFunction_default = isFunction;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_coreJsData.js
  var coreJsData = root_default["__core-js_shared__"];
  var coreJsData_default = coreJsData;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_isMasked.js
  var maskSrcKey = function() {
    var uid = /[^.]+$/.exec(coreJsData_default && coreJsData_default.keys && coreJsData_default.keys.IE_PROTO || "");
    return uid ? "Symbol(src)_1." + uid : "";
  }();
  function isMasked(func) {
    return !!maskSrcKey && maskSrcKey in func;
  }
  var isMasked_default = isMasked;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_toSource.js
  var funcProto = Function.prototype;
  var funcToString = funcProto.toString;
  function toSource(func) {
    if (func != null) {
      try {
        return funcToString.call(func);
      } catch (e) {
      }
      try {
        return func + "";
      } catch (e) {
      }
    }
    return "";
  }
  var toSource_default = toSource;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_baseIsNative.js
  var reRegExpChar = /[\\^$.*+?()[\]{}|]/g;
  var reIsHostCtor = /^\[object .+?Constructor\]$/;
  var funcProto2 = Function.prototype;
  var objectProto3 = Object.prototype;
  var funcToString2 = funcProto2.toString;
  var hasOwnProperty2 = objectProto3.hasOwnProperty;
  var reIsNative = RegExp("^" + funcToString2.call(hasOwnProperty2).replace(reRegExpChar, "\\$&").replace(/hasOwnProperty|(function).*?(?=\\\()| for .+?(?=\\\])/g, "$1.*?") + "$");
  function baseIsNative(value) {
    if (!isObject_default(value) || isMasked_default(value)) {
      return false;
    }
    var pattern = isFunction_default(value) ? reIsNative : reIsHostCtor;
    return pattern.test(toSource_default(value));
  }
  var baseIsNative_default = baseIsNative;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_getValue.js
  function getValue(object, key) {
    return object == null ? void 0 : object[key];
  }
  var getValue_default = getValue;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_getNative.js
  function getNative(object, key) {
    var value = getValue_default(object, key);
    return baseIsNative_default(value) ? value : void 0;
  }
  var getNative_default = getNative;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_apply.js
  function apply(func, thisArg, args) {
    switch (args.length) {
      case 0:
        return func.call(thisArg);
      case 1:
        return func.call(thisArg, args[0]);
      case 2:
        return func.call(thisArg, args[0], args[1]);
      case 3:
        return func.call(thisArg, args[0], args[1], args[2]);
    }
    return func.apply(thisArg, args);
  }
  var apply_default = apply;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_shortOut.js
  var HOT_COUNT = 800;
  var HOT_SPAN = 16;
  var nativeNow = Date.now;
  function shortOut(func) {
    var count = 0, lastCalled = 0;
    return function() {
      var stamp = nativeNow(), remaining = HOT_SPAN - (stamp - lastCalled);
      lastCalled = stamp;
      if (remaining > 0) {
        if (++count >= HOT_COUNT) {
          return arguments[0];
        }
      } else {
        count = 0;
      }
      return func.apply(void 0, arguments);
    };
  }
  var shortOut_default = shortOut;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/constant.js
  function constant(value) {
    return function() {
      return value;
    };
  }
  var constant_default = constant;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_defineProperty.js
  var defineProperty = function() {
    try {
      var func = getNative_default(Object, "defineProperty");
      func({}, "", {});
      return func;
    } catch (e) {
    }
  }();
  var defineProperty_default = defineProperty;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_baseSetToString.js
  var baseSetToString = !defineProperty_default ? identity_default : function(func, string) {
    return defineProperty_default(func, "toString", {
      "configurable": true,
      "enumerable": false,
      "value": constant_default(string),
      "writable": true
    });
  };
  var baseSetToString_default = baseSetToString;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_setToString.js
  var setToString = shortOut_default(baseSetToString_default);
  var setToString_default = setToString;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_isIndex.js
  var MAX_SAFE_INTEGER = 9007199254740991;
  var reIsUint = /^(?:0|[1-9]\d*)$/;
  function isIndex(value, length) {
    var type = typeof value;
    length = length == null ? MAX_SAFE_INTEGER : length;
    return !!length && (type == "number" || type != "symbol" && reIsUint.test(value)) && (value > -1 && value % 1 == 0 && value < length);
  }
  var isIndex_default = isIndex;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_baseAssignValue.js
  function baseAssignValue(object, key, value) {
    if (key == "__proto__" && defineProperty_default) {
      defineProperty_default(object, key, {
        "configurable": true,
        "enumerable": true,
        "value": value,
        "writable": true
      });
    } else {
      object[key] = value;
    }
  }
  var baseAssignValue_default = baseAssignValue;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/eq.js
  function eq(value, other) {
    return value === other || value !== value && other !== other;
  }
  var eq_default = eq;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_assignValue.js
  var objectProto4 = Object.prototype;
  var hasOwnProperty3 = objectProto4.hasOwnProperty;
  function assignValue(object, key, value) {
    var objValue = object[key];
    if (!(hasOwnProperty3.call(object, key) && eq_default(objValue, value)) || value === void 0 && !(key in object)) {
      baseAssignValue_default(object, key, value);
    }
  }
  var assignValue_default = assignValue;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_copyObject.js
  function copyObject(source, props, object, customizer) {
    var isNew = !object;
    object || (object = {});
    var index = -1, length = props.length;
    while (++index < length) {
      var key = props[index];
      var newValue = customizer ? customizer(object[key], source[key], key, object, source) : void 0;
      if (newValue === void 0) {
        newValue = source[key];
      }
      if (isNew) {
        baseAssignValue_default(object, key, newValue);
      } else {
        assignValue_default(object, key, newValue);
      }
    }
    return object;
  }
  var copyObject_default = copyObject;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_overRest.js
  var nativeMax = Math.max;
  function overRest(func, start, transform) {
    start = nativeMax(start === void 0 ? func.length - 1 : start, 0);
    return function() {
      var args = arguments, index = -1, length = nativeMax(args.length - start, 0), array = Array(length);
      while (++index < length) {
        array[index] = args[start + index];
      }
      index = -1;
      var otherArgs = Array(start + 1);
      while (++index < start) {
        otherArgs[index] = args[index];
      }
      otherArgs[start] = transform(array);
      return apply_default(func, this, otherArgs);
    };
  }
  var overRest_default = overRest;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_baseRest.js
  function baseRest(func, start) {
    return setToString_default(overRest_default(func, start, identity_default), func + "");
  }
  var baseRest_default = baseRest;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/isLength.js
  var MAX_SAFE_INTEGER2 = 9007199254740991;
  function isLength(value) {
    return typeof value == "number" && value > -1 && value % 1 == 0 && value <= MAX_SAFE_INTEGER2;
  }
  var isLength_default = isLength;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/isArrayLike.js
  function isArrayLike(value) {
    return value != null && isLength_default(value.length) && !isFunction_default(value);
  }
  var isArrayLike_default = isArrayLike;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_isIterateeCall.js
  function isIterateeCall(value, index, object) {
    if (!isObject_default(object)) {
      return false;
    }
    var type = typeof index;
    if (type == "number" ? isArrayLike_default(object) && isIndex_default(index, object.length) : type == "string" && index in object) {
      return eq_default(object[index], value);
    }
    return false;
  }
  var isIterateeCall_default = isIterateeCall;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_createAssigner.js
  function createAssigner(assigner) {
    return baseRest_default(function(object, sources) {
      var index = -1, length = sources.length, customizer = length > 1 ? sources[length - 1] : void 0, guard = length > 2 ? sources[2] : void 0;
      customizer = assigner.length > 3 && typeof customizer == "function" ? (length--, customizer) : void 0;
      if (guard && isIterateeCall_default(sources[0], sources[1], guard)) {
        customizer = length < 3 ? void 0 : customizer;
        length = 1;
      }
      object = Object(object);
      while (++index < length) {
        var source = sources[index];
        if (source) {
          assigner(object, source, index, customizer);
        }
      }
      return object;
    });
  }
  var createAssigner_default = createAssigner;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_isPrototype.js
  var objectProto5 = Object.prototype;
  function isPrototype(value) {
    var Ctor = value && value.constructor, proto = typeof Ctor == "function" && Ctor.prototype || objectProto5;
    return value === proto;
  }
  var isPrototype_default = isPrototype;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_baseTimes.js
  function baseTimes(n, iteratee) {
    var index = -1, result = Array(n);
    while (++index < n) {
      result[index] = iteratee(index);
    }
    return result;
  }
  var baseTimes_default = baseTimes;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_baseIsArguments.js
  var argsTag = "[object Arguments]";
  function baseIsArguments(value) {
    return isObjectLike_default(value) && baseGetTag_default(value) == argsTag;
  }
  var baseIsArguments_default = baseIsArguments;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/isArguments.js
  var objectProto6 = Object.prototype;
  var hasOwnProperty4 = objectProto6.hasOwnProperty;
  var propertyIsEnumerable = objectProto6.propertyIsEnumerable;
  var isArguments = baseIsArguments_default(function() {
    return arguments;
  }()) ? baseIsArguments_default : function(value) {
    return isObjectLike_default(value) && hasOwnProperty4.call(value, "callee") && !propertyIsEnumerable.call(value, "callee");
  };
  var isArguments_default = isArguments;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/stubFalse.js
  function stubFalse() {
    return false;
  }
  var stubFalse_default = stubFalse;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/isBuffer.js
  var freeExports = typeof exports == "object" && exports && !exports.nodeType && exports;
  var freeModule = freeExports && typeof module == "object" && module && !module.nodeType && module;
  var moduleExports = freeModule && freeModule.exports === freeExports;
  var Buffer2 = moduleExports ? root_default.Buffer : void 0;
  var nativeIsBuffer = Buffer2 ? Buffer2.isBuffer : void 0;
  var isBuffer = nativeIsBuffer || stubFalse_default;
  var isBuffer_default = isBuffer;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_baseIsTypedArray.js
  var argsTag2 = "[object Arguments]";
  var arrayTag = "[object Array]";
  var boolTag = "[object Boolean]";
  var dateTag = "[object Date]";
  var errorTag = "[object Error]";
  var funcTag2 = "[object Function]";
  var mapTag = "[object Map]";
  var numberTag = "[object Number]";
  var objectTag = "[object Object]";
  var regexpTag = "[object RegExp]";
  var setTag = "[object Set]";
  var stringTag = "[object String]";
  var weakMapTag = "[object WeakMap]";
  var arrayBufferTag = "[object ArrayBuffer]";
  var dataViewTag = "[object DataView]";
  var float32Tag = "[object Float32Array]";
  var float64Tag = "[object Float64Array]";
  var int8Tag = "[object Int8Array]";
  var int16Tag = "[object Int16Array]";
  var int32Tag = "[object Int32Array]";
  var uint8Tag = "[object Uint8Array]";
  var uint8ClampedTag = "[object Uint8ClampedArray]";
  var uint16Tag = "[object Uint16Array]";
  var uint32Tag = "[object Uint32Array]";
  var typedArrayTags = {};
  typedArrayTags[float32Tag] = typedArrayTags[float64Tag] = typedArrayTags[int8Tag] = typedArrayTags[int16Tag] = typedArrayTags[int32Tag] = typedArrayTags[uint8Tag] = typedArrayTags[uint8ClampedTag] = typedArrayTags[uint16Tag] = typedArrayTags[uint32Tag] = true;
  typedArrayTags[argsTag2] = typedArrayTags[arrayTag] = typedArrayTags[arrayBufferTag] = typedArrayTags[boolTag] = typedArrayTags[dataViewTag] = typedArrayTags[dateTag] = typedArrayTags[errorTag] = typedArrayTags[funcTag2] = typedArrayTags[mapTag] = typedArrayTags[numberTag] = typedArrayTags[objectTag] = typedArrayTags[regexpTag] = typedArrayTags[setTag] = typedArrayTags[stringTag] = typedArrayTags[weakMapTag] = false;
  function baseIsTypedArray(value) {
    return isObjectLike_default(value) && isLength_default(value.length) && !!typedArrayTags[baseGetTag_default(value)];
  }
  var baseIsTypedArray_default = baseIsTypedArray;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_baseUnary.js
  function baseUnary(func) {
    return function(value) {
      return func(value);
    };
  }
  var baseUnary_default = baseUnary;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_nodeUtil.js
  var freeExports2 = typeof exports == "object" && exports && !exports.nodeType && exports;
  var freeModule2 = freeExports2 && typeof module == "object" && module && !module.nodeType && module;
  var moduleExports2 = freeModule2 && freeModule2.exports === freeExports2;
  var freeProcess = moduleExports2 && freeGlobal_default.process;
  var nodeUtil = function() {
    try {
      var types = freeModule2 && freeModule2.require && freeModule2.require("util").types;
      if (types) {
        return types;
      }
      return freeProcess && freeProcess.binding && freeProcess.binding("util");
    } catch (e) {
    }
  }();
  var nodeUtil_default = nodeUtil;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/isTypedArray.js
  var nodeIsTypedArray = nodeUtil_default && nodeUtil_default.isTypedArray;
  var isTypedArray = nodeIsTypedArray ? baseUnary_default(nodeIsTypedArray) : baseIsTypedArray_default;
  var isTypedArray_default = isTypedArray;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_arrayLikeKeys.js
  var objectProto7 = Object.prototype;
  var hasOwnProperty5 = objectProto7.hasOwnProperty;
  function arrayLikeKeys(value, inherited) {
    var isArr = isArray_default(value), isArg = !isArr && isArguments_default(value), isBuff = !isArr && !isArg && isBuffer_default(value), isType = !isArr && !isArg && !isBuff && isTypedArray_default(value), skipIndexes = isArr || isArg || isBuff || isType, result = skipIndexes ? baseTimes_default(value.length, String) : [], length = result.length;
    for (var key in value) {
      if ((inherited || hasOwnProperty5.call(value, key)) && !(skipIndexes && (key == "length" || isBuff && (key == "offset" || key == "parent") || isType && (key == "buffer" || key == "byteLength" || key == "byteOffset") || isIndex_default(key, length)))) {
        result.push(key);
      }
    }
    return result;
  }
  var arrayLikeKeys_default = arrayLikeKeys;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_overArg.js
  function overArg(func, transform) {
    return function(arg) {
      return func(transform(arg));
    };
  }
  var overArg_default = overArg;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_nativeKeys.js
  var nativeKeys = overArg_default(Object.keys, Object);
  var nativeKeys_default = nativeKeys;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_baseKeys.js
  var objectProto8 = Object.prototype;
  var hasOwnProperty6 = objectProto8.hasOwnProperty;
  function baseKeys(object) {
    if (!isPrototype_default(object)) {
      return nativeKeys_default(object);
    }
    var result = [];
    for (var key in Object(object)) {
      if (hasOwnProperty6.call(object, key) && key != "constructor") {
        result.push(key);
      }
    }
    return result;
  }
  var baseKeys_default = baseKeys;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/keys.js
  function keys(object) {
    return isArrayLike_default(object) ? arrayLikeKeys_default(object) : baseKeys_default(object);
  }
  var keys_default = keys;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_nativeKeysIn.js
  function nativeKeysIn(object) {
    var result = [];
    if (object != null) {
      for (var key in Object(object)) {
        result.push(key);
      }
    }
    return result;
  }
  var nativeKeysIn_default = nativeKeysIn;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_baseKeysIn.js
  var objectProto9 = Object.prototype;
  var hasOwnProperty7 = objectProto9.hasOwnProperty;
  function baseKeysIn(object) {
    if (!isObject_default(object)) {
      return nativeKeysIn_default(object);
    }
    var isProto = isPrototype_default(object), result = [];
    for (var key in object) {
      if (!(key == "constructor" && (isProto || !hasOwnProperty7.call(object, key)))) {
        result.push(key);
      }
    }
    return result;
  }
  var baseKeysIn_default = baseKeysIn;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/keysIn.js
  function keysIn(object) {
    return isArrayLike_default(object) ? arrayLikeKeys_default(object, true) : baseKeysIn_default(object);
  }
  var keysIn_default = keysIn;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/assignInWith.js
  var assignInWith = createAssigner_default(function(object, source, srcIndex, customizer) {
    copyObject_default(source, keysIn_default(source), object, customizer);
  });
  var assignInWith_default = assignInWith;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/toString.js
  function toString(value) {
    return value == null ? "" : baseToString_default(value);
  }
  var toString_default = toString;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_getPrototype.js
  var getPrototype = overArg_default(Object.getPrototypeOf, Object);
  var getPrototype_default = getPrototype;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/isPlainObject.js
  var objectTag2 = "[object Object]";
  var funcProto3 = Function.prototype;
  var objectProto10 = Object.prototype;
  var funcToString3 = funcProto3.toString;
  var hasOwnProperty8 = objectProto10.hasOwnProperty;
  var objectCtorString = funcToString3.call(Object);
  function isPlainObject(value) {
    if (!isObjectLike_default(value) || baseGetTag_default(value) != objectTag2) {
      return false;
    }
    var proto = getPrototype_default(value);
    if (proto === null) {
      return true;
    }
    var Ctor = hasOwnProperty8.call(proto, "constructor") && proto.constructor;
    return typeof Ctor == "function" && Ctor instanceof Ctor && funcToString3.call(Ctor) == objectCtorString;
  }
  var isPlainObject_default = isPlainObject;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/isError.js
  var domExcTag = "[object DOMException]";
  var errorTag2 = "[object Error]";
  function isError(value) {
    if (!isObjectLike_default(value)) {
      return false;
    }
    var tag = baseGetTag_default(value);
    return tag == errorTag2 || tag == domExcTag || typeof value.message == "string" && typeof value.name == "string" && !isPlainObject_default(value);
  }
  var isError_default = isError;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/attempt.js
  var attempt = baseRest_default(function(func, args) {
    try {
      return apply_default(func, void 0, args);
    } catch (e) {
      return isError_default(e) ? e : new Error(e);
    }
  });
  var attempt_default = attempt;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_basePropertyOf.js
  function basePropertyOf(object) {
    return function(key) {
      return object == null ? void 0 : object[key];
    };
  }
  var basePropertyOf_default = basePropertyOf;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_escapeHtmlChar.js
  var htmlEscapes = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  };
  var escapeHtmlChar = basePropertyOf_default(htmlEscapes);
  var escapeHtmlChar_default = escapeHtmlChar;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/escape.js
  var reUnescapedHtml = /[&<>"']/g;
  var reHasUnescapedHtml = RegExp(reUnescapedHtml.source);
  function escape(string) {
    string = toString_default(string);
    return string && reHasUnescapedHtml.test(string) ? string.replace(reUnescapedHtml, escapeHtmlChar_default) : string;
  }
  var escape_default = escape;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_baseValues.js
  function baseValues(object, props) {
    return arrayMap_default(props, function(key) {
      return object[key];
    });
  }
  var baseValues_default = baseValues;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_customDefaultsAssignIn.js
  var objectProto11 = Object.prototype;
  var hasOwnProperty9 = objectProto11.hasOwnProperty;
  function customDefaultsAssignIn(objValue, srcValue, key, object) {
    if (objValue === void 0 || eq_default(objValue, objectProto11[key]) && !hasOwnProperty9.call(object, key)) {
      return srcValue;
    }
    return objValue;
  }
  var customDefaultsAssignIn_default = customDefaultsAssignIn;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_escapeStringChar.js
  var stringEscapes = {
    "\\": "\\",
    "'": "'",
    "\n": "n",
    "\r": "r",
    "\u2028": "u2028",
    "\u2029": "u2029"
  };
  function escapeStringChar(chr) {
    return "\\" + stringEscapes[chr];
  }
  var escapeStringChar_default = escapeStringChar;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_reInterpolate.js
  var reInterpolate = /<%=([\s\S]+?)%>/g;
  var reInterpolate_default = reInterpolate;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_reEscape.js
  var reEscape = /<%-([\s\S]+?)%>/g;
  var reEscape_default = reEscape;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/_reEvaluate.js
  var reEvaluate = /<%([\s\S]+?)%>/g;
  var reEvaluate_default = reEvaluate;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/templateSettings.js
  var templateSettings = {
    "escape": reEscape_default,
    "evaluate": reEvaluate_default,
    "interpolate": reInterpolate_default,
    "variable": "",
    "imports": {
      "_": { "escape": escape_default }
    }
  };
  var templateSettings_default = templateSettings;

  // node_modules/.pnpm/registry.nlark.com+lodash-es@4.17.21/node_modules/lodash-es/template.js
  var INVALID_TEMPL_VAR_ERROR_TEXT = "Invalid `variable` option passed into `_.template`";
  var reEmptyStringLeading = /\b__p \+= '';/g;
  var reEmptyStringMiddle = /\b(__p \+=) '' \+/g;
  var reEmptyStringTrailing = /(__e\(.*?\)|\b__t\)) \+\n'';/g;
  var reForbiddenIdentifierChars = /[()=,{}\[\]\/\s]/;
  var reEsTemplate = /\$\{([^\\}]*(?:\\.[^\\}]*)*)\}/g;
  var reNoMatch = /($^)/;
  var reUnescapedString = /['\n\r\u2028\u2029\\]/g;
  var objectProto12 = Object.prototype;
  var hasOwnProperty10 = objectProto12.hasOwnProperty;
  function template(string, options, guard) {
    var settings = templateSettings_default.imports._.templateSettings || templateSettings_default;
    if (guard && isIterateeCall_default(string, options, guard)) {
      options = void 0;
    }
    string = toString_default(string);
    options = assignInWith_default({}, options, settings, customDefaultsAssignIn_default);
    var imports = assignInWith_default({}, options.imports, settings.imports, customDefaultsAssignIn_default), importsKeys = keys_default(imports), importsValues = baseValues_default(imports, importsKeys);
    var isEscaping, isEvaluating, index = 0, interpolate = options.interpolate || reNoMatch, source = "__p += '";
    var reDelimiters = RegExp((options.escape || reNoMatch).source + "|" + interpolate.source + "|" + (interpolate === reInterpolate_default ? reEsTemplate : reNoMatch).source + "|" + (options.evaluate || reNoMatch).source + "|$", "g");
    var sourceURL = hasOwnProperty10.call(options, "sourceURL") ? "//# sourceURL=" + (options.sourceURL + "").replace(/\s/g, " ") + "\n" : "";
    string.replace(reDelimiters, function(match, escapeValue, interpolateValue, esTemplateValue, evaluateValue, offset) {
      interpolateValue || (interpolateValue = esTemplateValue);
      source += string.slice(index, offset).replace(reUnescapedString, escapeStringChar_default);
      if (escapeValue) {
        isEscaping = true;
        source += "' +\n__e(" + escapeValue + ") +\n'";
      }
      if (evaluateValue) {
        isEvaluating = true;
        source += "';\n" + evaluateValue + ";\n__p += '";
      }
      if (interpolateValue) {
        source += "' +\n((__t = (" + interpolateValue + ")) == null ? '' : __t) +\n'";
      }
      index = offset + match.length;
      return match;
    });
    source += "';\n";
    var variable = hasOwnProperty10.call(options, "variable") && options.variable;
    if (!variable) {
      source = "with (obj) {\n" + source + "\n}\n";
    } else if (reForbiddenIdentifierChars.test(variable)) {
      throw new Error(INVALID_TEMPL_VAR_ERROR_TEXT);
    }
    source = (isEvaluating ? source.replace(reEmptyStringLeading, "") : source).replace(reEmptyStringMiddle, "$1").replace(reEmptyStringTrailing, "$1;");
    source = "function(" + (variable || "obj") + ") {\n" + (variable ? "" : "obj || (obj = {});\n") + "var __t, __p = ''" + (isEscaping ? ", __e = _.escape" : "") + (isEvaluating ? ", __j = Array.prototype.join;\nfunction print() { __p += __j.call(arguments, '') }\n" : ";\n") + source + "return __p\n}";
    var result = attempt_default(function() {
      return Function(importsKeys, sourceURL + "return " + source).apply(void 0, importsValues);
    });
    result.source = source;
    if (isError_default(result)) {
      throw result;
    }
    return result;
  }
  var template_default = template;

  // assets/style.css
  var style_default = "/*! tailwindcss v2.2.19 | MIT License | https://tailwindcss.com*//*! modern-normalize v1.1.0 | MIT License | https://github.com/sindresorhus/modern-normalize */html{-moz-tab-size:4;-o-tab-size:4;tab-size:4;line-height:1.15;-webkit-text-size-adjust:100%}body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif,Apple Color Emoji,Segoe UI Emoji}hr{height:0;color:inherit}abbr[title]{-webkit-text-decoration:underline dotted;text-decoration:underline dotted}b,strong{font-weight:bolder}code,kbd,pre,samp{font-family:ui-monospace,SFMono-Regular,Consolas,Liberation Mono,Menlo,monospace;font-size:1em}small{font-size:80%}sub,sup{font-size:75%;line-height:0;position:relative;vertical-align:initial}sub{bottom:-.25em}sup{top:-.5em}table{text-indent:0;border-color:inherit}button,input,optgroup,select,textarea{font-family:inherit;font-size:100%;line-height:1.15;margin:0}button,select{text-transform:none}button{-webkit-appearance:button}legend{padding:0}progress{vertical-align:initial}summary{display:list-item}blockquote,dd,dl,figure,h1,h2,h3,h4,h5,h6,hr,p,pre{margin:0}button{background-color:initial;background-image:none}fieldset,ol,ul{margin:0;padding:0}ol,ul{list-style:none}html{font-family:ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica Neue,Arial,Noto Sans,sans-serif,Apple Color Emoji,Segoe UI Emoji,Segoe UI Symbol,Noto Color Emoji;line-height:1.5}body{font-family:inherit;line-height:inherit}*,:after,:before{box-sizing:border-box;border:0 solid}hr{border-top-width:1px}img{border-style:solid}textarea{resize:vertical}input::-moz-placeholder,textarea::-moz-placeholder{opacity:1;color:#9ca3af}input:-ms-input-placeholder,textarea:-ms-input-placeholder{opacity:1;color:#9ca3af}input::placeholder,textarea::placeholder{opacity:1;color:#9ca3af}button{cursor:pointer}table{border-collapse:collapse}h1,h2,h3,h4,h5,h6{font-size:inherit;font-weight:inherit}a{color:inherit;text-decoration:inherit}button,input,optgroup,select,textarea{padding:0;line-height:inherit;color:inherit}code,kbd,pre,samp{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,Liberation Mono,Courier New,monospace}audio,canvas,embed,iframe,img,object,svg,video{display:block;vertical-align:middle}img,video{max-width:100%;height:auto}*,:after,:before{--tw-border-opacity:1;border-color:rgba(229,231,235,var(--tw-border-opacity))}.container{width:100%}@media (min-width:640px){.container{max-width:640px}}@media (min-width:768px){.container{max-width:768px}}@media (min-width:1024px){.container{max-width:1024px}}@media (min-width:1280px){.container{max-width:1280px}}@media (min-width:1536px){.container{max-width:1536px}}.m-auto{margin:auto}.block{display:block}.table{display:table}@-webkit-keyframes spin{to{transform:rotate(1turn)}}@keyframes spin{to{transform:rotate(1turn)}}@-webkit-keyframes ping{75%,to{transform:scale(2);opacity:0}}@keyframes ping{75%,to{transform:scale(2);opacity:0}}@-webkit-keyframes pulse{50%{opacity:.5}}@keyframes pulse{50%{opacity:.5}}@-webkit-keyframes bounce{0%,to{transform:translateY(-25%);-webkit-animation-timing-function:cubic-bezier(.8,0,1,1);animation-timing-function:cubic-bezier(.8,0,1,1)}50%{transform:none;-webkit-animation-timing-function:cubic-bezier(0,0,.2,1);animation-timing-function:cubic-bezier(0,0,.2,1)}}@keyframes bounce{0%,to{transform:translateY(-25%);-webkit-animation-timing-function:cubic-bezier(.8,0,1,1);animation-timing-function:cubic-bezier(.8,0,1,1)}50%{transform:none;-webkit-animation-timing-function:cubic-bezier(0,0,.2,1);animation-timing-function:cubic-bezier(0,0,.2,1)}}.border{border-width:1px}.text-center{text-align:center}.text-lg{font-size:1.125rem;line-height:1.75rem}.font-bold{font-weight:700}.text-blue-400{--tw-text-opacity:1;color:rgba(96,165,250,var(--tw-text-opacity))}.underline{text-decoration:underline}*,:after,:before{--tw-shadow:0 0 #0000;--tw-ring-inset:var(--tw-empty,/*!*/ /*!*/);--tw-ring-offset-width:0px;--tw-ring-offset-color:#fff;--tw-ring-color:rgba(59,130,246,0.5);--tw-ring-offset-shadow:0 0 #0000;--tw-ring-shadow:0 0 #0000}@media (min-width:640px){.sm\\:space-y-2>:not([hidden])~:not([hidden]){--tw-space-y-reverse:0;margin-top:calc(.5rem*(1 - var(--tw-space-y-reverse)));margin-bottom:calc(.5rem*var(--tw-space-y-reverse))}}@media (min-width:768px){.md\\:space-y-4>:not([hidden])~:not([hidden]){--tw-space-y-reverse:0;margin-top:calc(1rem*(1 - var(--tw-space-y-reverse)));margin-bottom:calc(1rem*var(--tw-space-y-reverse))}}";

  // utils/imageToCanvas.ts
  function imageToCanvas(img, {
    background
  } = {}) {
    const canvas = document.createElement("canvas");
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    const ctx = canvas.getContext("2d");
    if (background) {
      ctx.fillStyle = background;
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    }
    ctx.drawImage(img, 0, 0);
    return canvas;
  }

  // niconico_manga_download.ts
  var __name__ = "NicoNico manga download";
  (function() {
    return __async(this, null, function* () {
      var _a, _b, _c;
      const images = [];
      const title = (_b = (_a = document.querySelector("meta[property='og:title']")) == null ? void 0 : _a.content) != null ? _b : document.title;
      const startTime = Date.now();
      const loopNext = () => {
        if (Date.now() - startTime < 3e5) {
          return true;
        }
        throw new Error(`${__name__}: timeout`);
      };
      const pages = document.querySelectorAll("li.page");
      for (let index = 0; index < pages.length; index += 1) {
        const li = pages.item(index);
        while (loopNext()) {
          const pageIndex = Number.parseInt(li.dataset.pageIndex, 10) || index;
          let canvas = li.querySelector("canvas:not(.balloon)");
          const image = li.querySelector("img[data-image-id]");
          if (image) {
            canvas != null ? canvas : canvas = imageToCanvas(image);
          }
          if (!canvas || canvas.width === 1) {
            li.scrollIntoView();
            console.log(`${__name__}: waiting page: ${pageIndex}`);
            yield sleep(1e3);
            continue;
          }
          images.push({
            src: canvas.toDataURL(),
            alt: li.id,
            title: `p${pageIndex + 1}`
          });
          break;
        }
      }
      (_c = pages.item(0)) == null ? void 0 : _c.scrollIntoView();
      const data = template_default(manga_reader_default)({
        title,
        window,
        images,
        style: style_default
      });
      console.log(`${__name__}: got ${images.length} page(s)`);
      const file = new Blob([data], { type: "text/html" });
      downloadFile(file, `${title}.html`);
    });
  })();
})();
/**
 * @license
 * Lodash (Custom Build) <https://lodash.com/>
 * Build: `lodash modularize exports="es" -o ./`
 * Copyright OpenJS Foundation and other contributors <https://openjsf.org/>
 * Released under MIT license <https://lodash.com/license>
 * Based on Underscore.js 1.8.3 <http://underscorejs.org/LICENSE>
 * Copyright Jeremy Ashkenas, DocumentCloud and Investigative Reporters & Editors
 */
