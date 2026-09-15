class lol.server.mess.CSM_E_get_si extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_E_get_si(typeID)
   {
      super();
      this._name = "e_get_si";
      this.addProp("type",typeID);
   }
}
