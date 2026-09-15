class lol.server.mess.CSM_TS_get_si extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_TS_get_si(typeID)
   {
      super();
      this._name = "ts_get_si";
      this.addProp("type",typeID);
   }
}
