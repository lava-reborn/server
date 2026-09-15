class lol.server.mess.CSM_GM_RemoveMark extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_GM_RemoveMark(id)
   {
      super();
      this._name = "rmMark";
      this.addProp("id",id);
   }
}
