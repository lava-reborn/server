class lol.server.mess.CSM_GM_UpdMark extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_GM_UpdMark(id, title, info)
   {
      super();
      this._name = "updMark";
      this.addProp("info",info);
      this.addProp("title",title);
      this.addProp("id",id);
   }
}
