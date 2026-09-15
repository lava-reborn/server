class lol.server.incmess.SCCommand
{
   var _commandParams;
   var _dispatcher;
   var _parser;
   var _source;
   var messID;
   function SCCommand(mID, src, parser)
   {
      this.messID = mID;
      this._source = src;
      this._parser = parser;
      this.init();
   }
   function get params()
   {
      return this._commandParams;
   }
   function setDispatcher(dispatcher)
   {
      this._dispatcher = dispatcher;
   }
   function init()
   {
      this._commandParams = new Object();
   }
   function execute()
   {
      if(this._dispatcher)
      {
         this._dispatcher.sendNotification(this);
      }
   }
   function getI(paramName)
   {
      return this._parser.getValueIndex(this._source,paramName);
   }
}
