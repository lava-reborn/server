class lol.server.mess.CSM_M_uldml extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_M_uldml(id)
   {
      super();
      this._name = "uldml";
      this.addProp("id",id);
   }
}
