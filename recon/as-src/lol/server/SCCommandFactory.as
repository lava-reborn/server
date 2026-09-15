class lol.server.SCCommandFactory
{
   var _cmdMap;
   var _parser;
   function SCCommandFactory()
   {
      this._parser = new lol.server.SCDataParser();
      this.init();
   }
   function init()
   {
      this._cmdMap = new Object();
   }
   function create(source)
   {
      var _loc3_ = this._parser.getCmdName(source);
      var _loc2_ = new lol.server.incmess.UniSCCommand(_loc3_,source,this._parser);
      return _loc2_;
   }
}
