class lol.server.mess.CSM_GM_InsMark extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_GM_InsMark(dx, dy, title, info)
   {
      super();
      this._name = "insMark";
      this.addProp("info",info);
      this.addProp("title",title);
      this.addProp("dy",dy);
      this.addProp("dx",dx);
   }
}
