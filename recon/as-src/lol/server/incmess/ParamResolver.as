class lol.server.incmess.ParamResolver
{
   var _$$$_commandParams;
   var _$$$_parser;
   var _$$$_source;
   function ParamResolver(str, parser)
   {
      this._$$$_source = str;
      this._$$$_parser = parser;
      this._$$$_commandParams = new Array();
   }
   function getCommandParams()
   {
      return this._$$$_commandParams;
   }
   function writeParam(paramName, value)
   {
      this._$$$_commandParams[paramName] = value;
   }
   function __resolve(paramName)
   {
      var _loc2_;
      _loc2_ = this._$$$_commandParams[paramName];
      if(_loc2_ == null || _loc2_ == undefined)
      {
         _loc2_ = this._$$$_parseParam(paramName);
         this._$$$_commandParams[paramName] = _loc2_;
      }
      return _loc2_;
   }
   function _$$$_parseParam(paramName)
   {
      return this._$$$_parser.getData(this._$$$_source,paramName);
   }
   function toString()
   {
      var _loc2_ = "[Params{";
      for(var _loc3_ in this._$$$_commandParams)
      {
         _loc2_ += _loc3_ + ":" + this._$$$_commandParams[_loc3_] + ", ";
      }
      _loc2_ += "}]";
      return _loc2_;
   }
}
