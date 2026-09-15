class lol.server.mess.CSM_C_GG_Info extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_C_GG_Info(det)
   {
      super();
      this._name = "gg_info";
      this.addProp("det",det);
   }
}
