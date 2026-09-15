class lol.server.mess.CSM_GM_InterceptPlayer extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_GM_InterceptPlayer(targetID)
   {
      super();
      this._name = "moveTo";
      this.addProp("trg",targetID);
   }
}
