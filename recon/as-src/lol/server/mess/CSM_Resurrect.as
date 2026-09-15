class lol.server.mess.CSM_Resurrect extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_Resurrect(res_type)
   {
      super();
      this._name = "resurrect";
      this.addProp("res_type",res_type);
   }
}
