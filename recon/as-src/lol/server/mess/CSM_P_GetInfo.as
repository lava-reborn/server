class lol.server.mess.CSM_P_GetInfo extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_P_GetInfo(type, id, lvl)
   {
      super();
      this._name = "getInfo";
      this.addProp("lvl",lvl);
      this.addProp("id",id);
      this.addProp("type",type);
   }
}
