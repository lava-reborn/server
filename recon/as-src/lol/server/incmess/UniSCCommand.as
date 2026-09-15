class lol.server.incmess.UniSCCommand extends lol.server.incmess.SCCommand
{
   var _commandParams;
   var _parser;
   var _source;
   function UniSCCommand(mID, src, parser)
   {
      super(mID,src,parser);
   }
   function execute()
   {
      this._commandParams = this._parser.parse(this._source);
      super.execute();
   }
}
