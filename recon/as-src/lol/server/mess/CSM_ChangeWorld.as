class lol.server.mess.CSM_ChangeWorld extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_ChangeWorld(to)
   {
      super();
      this._name = "chWorld";
      this.addProp("to",to);
   }
}
