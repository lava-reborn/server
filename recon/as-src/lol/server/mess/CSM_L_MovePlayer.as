class lol.server.mess.CSM_L_MovePlayer extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_L_MovePlayer(path)
   {
      super();
      this._name = "moveTo";
      this.addProp("path",path);
   }
}
