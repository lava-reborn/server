class lol.server.mess.CSM_E_get_di extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_E_get_di(typeID, mobID)
   {
      super();
      this._name = "e_get_di";
      this.addProp("type",typeID);
      this.addProp("mobi_id",mobID);
   }
}
