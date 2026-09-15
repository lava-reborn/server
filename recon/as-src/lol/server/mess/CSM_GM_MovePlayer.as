class lol.server.mess.CSM_GM_MovePlayer extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_GM_MovePlayer(dx, dy)
   {
      super();
      this._name = "moveTo";
      this.addProp("dy",dy);
      this.addProp("dx",dx);
   }
}
