class lol.server.mess.CSM_SSMove extends lol.server.mess.CSMessage
{
   var _name;
   function CSM_SSMove(from, to, obj)
   {
      super();
      this._name = "ss_move";
      this.addProp("obj",obj);
      this.addProp("to",to);
      this.addProp("from",from);
   }
}
